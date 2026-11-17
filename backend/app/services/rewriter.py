# rewriter.py file converts a user's latest message into a standalone question
# using the previous chat history, so the RAG system can search the documents with a clear question.
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm import get_llm, message_text

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 6 # use only the last 6 messages from the chat
MAX_CHARS_PER_MESSAGE = 500 # cut each old message to 500 characters (keeps the prompt small)

# # Instructions for the AI: turn the student's message into a clean topic question
REWRITE_PROMPT = """Rewrite the user's latest message as one standalone question.

Rules:
- Use conversation history to resolve references like "it", "that", "why", and "what didn't you find".
- Always prioritize the most recent relevant conversation.
- Identify the original user question associated with the latest assistant response.
- If the assistant said it could not find information, preserve the topic of the original unanswered question.
- For example:
  User: Tell me how to cook biryani?
  Assistant: I couldn't find this in your documents.
  User: Why don't you know about it?
  Assistant: I couldn't find this in your documents.
  User: What didn't you find?
  Rewrite: What information about cooking biryani could not be found in the documents?
- Never replace a specific topic with a generic question when the topic is available in history.
- If the latest message is already a clear, standalone question, return it unchanged.
- Do not answer the question or invent information.
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

