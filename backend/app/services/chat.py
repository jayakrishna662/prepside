import logging
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.services.llm import get_llm, message_text
from app.services.rag import NOT_FOUND_MESSAGE, answer_question
from app.services.rewriter import (
    MAX_HISTORY_MESSAGES,
    analyze_message,
    format_transcript,
)

logger = logging.getLogger(__name__)



SCOPE_MESSAGE = (
    "I'm designed to answer questions using your uploaded documents "
    "and their context. I can't answer general questions outside "
    "that scope."
)


def get_history(
    db: Session,
    conversation_id: uuid.UUID,
) -> list[tuple[str, str]]:
    """Retrieve recent messages in chronological order."""

    rows = db.execute(
        select(Message.role, Message.content)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    ).all()

    return [(role, content) for role, content in reversed(rows)]



def get_failed_question(
    history: list[tuple[str, str]],
) -> str | None:
    """
    Find the latest user question associated with an unsuccessful search.

    Also recognizes the scope response from older conversations,
    where a question may have been rejected before document retrieval.
    """

    failure_responses = {
        NOT_FOUND_MESSAGE.strip(),
        SCOPE_MESSAGE.strip(),
    }

    for index in range(len(history) - 1, -1, -1):
        role, content = history[index]

        if role != "assistant":
            continue

        is_failed_search = content.strip() in failure_responses

        # Recognize contextual failed-search explanations from
        # previous versions of this workflow.
        if (
            not is_failed_search
            and "couldn't find relevant information to answer"
            in content.lower()
        ):
            is_failed_search = True

        if is_failed_search:
            for previous_role, previous_content in reversed(
                history[:index]
            ):
                if previous_role == "user":
                    return previous_content

    return None


def generate_search_clarification(
    history: list[tuple[str, str]],
    failed_question: str,
    question: str,
) -> str:
    """Explain briefly what the previous search could not find."""

    prompt = f"""
You are an enterprise knowledge assistant.

Earlier user question:
{failed_question}

The document search did not find enough relevant information
to answer that question.

Conversation history:
{format_transcript(history)}

Latest user message:
{question}

Explain what information the search could not find.

Rules:
- Answer in 1 or 2 short sentences, maximum 35 words.
- Directly address the user's question.
- Use simple, natural language.
- Explain what information was not retrieved based on the original question.
- Do not invent document contents.
- Do not claim that information is absent from all documents unless verified.
- Do not answer using general knowledge.
- Do not give a lengthy explanation.
"""

    try:
        response = get_llm().invoke(
            [
                SystemMessage(
                    content=(
                        "Explain unsuccessful document searches accurately "
                        "and concisely."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )

        answer_text = message_text(response).strip()

        if not answer_text:
            raise ValueError("Empty clarification response")

        return answer_text

    except Exception:
        logger.exception("Failed to generate search clarification")

        return (
            f"I couldn't find enough relevant information to answer "
            f"'{failed_question}'. The search may not have retrieved "
            "relevant content."
        )


def citations_to_dicts(citations) -> list[dict]:
    """Convert Citation objects into the JSON shape saved in messages.citations."""
    return [
        {
            "document_id": str(c.document_id),
            "filename": c.filename,
            "page": c.page,
            "has_image": c.has_image,
        }
        for c in citations
    ]



def ask(
    db: Session,
    user_id: uuid.UUID,
    conversation: Conversation,
    question: str,
) -> Message:
    """Process a message, retrieve relevant documents, and save the answer."""

    # Step 1: Retrieve recent conversation history.
    history = get_history(db, conversation.id)

    # Step 2: Classify the user's intent.
    intent, standalone = analyze_message(history, question)
    logger.info("Detected intent: %s", intent)
    logger.info("Original question: %s", question)
    logger.info("Rewritten question: %s", standalone)

    # Step 3: A "clarification" needs a failed search to explain.
    # If there isn't one, treat the message as a normal question.
    failed_question = None
    if intent == "SEARCH_CLARIFICATION":
        failed_question = get_failed_question(history)
        if failed_question is None:
            intent = "NEW_QUESTION"

    # Step 4: Build the answer.
    if intent == "SEARCH_CLARIFICATION":
        # Explain the earlier failed search, with no new retrieval.
        answer_text = generate_search_clarification(
            history=history,
            failed_question=failed_question,
            question=question,
        )
        found = False
        citations = []
    else:
        answer = answer_question(
            db,
            user_id,
            standalone,
            student_message=question,
        )

        if intent == "SCOPE_QUESTION" and not answer.found:
            # The documents can't answer, and the user is asking about
            # the assistant's limits, so explain the scope.
            answer_text = SCOPE_MESSAGE
            found = False
            citations = []
        else:
            answer_text = answer.answer
            found = answer.found
            citations = citations_to_dicts(answer.citations)

    # Step 6: Save the user's message.
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=question,
    )

    db.add(user_msg)
    db.flush()

    # Step 7: Save the assistant's response.
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_text,
        found=found,
        citations=citations,
    )

    db.add(assistant_msg)

    # Step 8: Update conversation metadata.
    if not history:
        conversation.title = question.strip()[:60] or "New chat"

    conversation.updated_at = func.now()

    # Step 9: Commit and return the saved response.
    db.commit()
    db.refresh(assistant_msg)

    return assistant_msg
