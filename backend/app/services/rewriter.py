# rewriter.py file converts a user's latest message into a standalone question
# using the previous chat history, so the RAG system can search the documents with a clear question.
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm import get_llm, message_text

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 6 # use only the last 6 messages from the chat
MAX_CHARS_PER_MESSAGE = 500 # cut each old message to 500 characters (keeps the prompt small)

# # Instructions for the AI: turn the student's message into a clean topic question
REWRITE_PROMPT = """Rewrite the student's latest message as one standalone question about the TOPIC, so it can be used to search their study material.

Rules:
- Use the chat history only to resolve references such as "it", "that" or "the previous one", and to recover the topic when the message only gives instructions (for example "make it longer").
- Remove instructions about the answer's length, format or style (for example "in 50 lines", "for 15 marks", "in detail", "in simple words", "as bullet points"). Keep only the topic.
- If the message is already a plain topic question, return it unchanged.
- Do not answer the question. Do not add information that is not in the chat history.
- Return only the rewritten question, nothing else."""


def condense_question(history: list[tuple[str, str]], question: str) -> str:
    """history is a list of (role, content) pairs, oldest first."""

    # If its First message of the chat: use the original question.
    if not history:
        return question

    # Take only the last few messages
    recent = history[-MAX_HISTORY_MESSAGES:]

    # Combine the previous messages(which contains messages with the roles) into a readable conversation transcript.
    # Limit each message to avoid sending too much text to the LLM.
    transcript = "\n".join(
        f"{role}: {content[:MAX_CHARS_PER_MESSAGE]}" for role, content in recent
    )

    # Combine the chat history and the new message into one prompt
    prompt = f"Chat history:\n{transcript}\n\nLatest message: {question}"

    try:
        # Ask the AI to rewrite the question
        reply = get_llm().invoke(
            [SystemMessage(content=REWRITE_PROMPT), HumanMessage(content=prompt)]
        )
        rewritten = message_text(reply).strip() #  if the AI returns empty text, use the original
        return rewritten or question
    except Exception:
        #  If the AI call fails, don't crash; just use the original question
        logger.exception("Question rewrite failed, using the original question")
        return question