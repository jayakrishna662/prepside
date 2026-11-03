import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm import get_llm, message_text

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 6
MAX_CHARS_PER_MESSAGE = 500

REWRITE_PROMPT = """Rewrite the student's latest message as one standalone question about the TOPIC, so it can be used to search their study material.

Rules:
- Use the chat history only to resolve references such as "it", "that" or "the previous one", and to recover the topic when the message only gives instructions (for example "make it longer").
- Remove instructions about the answer's length, format or style (for example "in 50 lines", "for 15 marks", "in detail", "in simple words", "as bullet points"). Keep only the topic.
- If the message is already a plain topic question, return it unchanged.
- Do not answer the question. Do not add information that is not in the chat history.
- Return only the rewritten question, nothing else."""


def condense_question(history: list[tuple[str, str]], question: str) -> str:
    """history is a list of (role, content) pairs, oldest first."""
    if not history:
        return question

    recent = history[-MAX_HISTORY_MESSAGES:]
    transcript = "\n".join(
        f"{role}: {content[:MAX_CHARS_PER_MESSAGE]}" for role, content in recent
    )
    prompt = f"Chat history:\n{transcript}\n\nLatest message: {question}"

    try:
        reply = get_llm().invoke(
            [SystemMessage(content=REWRITE_PROMPT), HumanMessage(content=prompt)]
        )
        rewritten = message_text(reply).strip()
        return rewritten or question
    except Exception:
        logger.exception("Question rewrite failed, using the original question")
        return question