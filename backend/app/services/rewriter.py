# rewriter.py understands the user's latest message using the chat history.
# One Gemini call returns two things:
#   1. the intent (new question, follow-up, search clarification, scope question)
#   2. the message rewritten as a standalone question for document search
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.services.llm import get_llm

logger = logging.getLogger(__name__)

# How much chat history is sent to the AI.
MAX_HISTORY_MESSAGES = 6      # use only the last 6 messages of the chat
MAX_CHARS_PER_MESSAGE = 500   # cut each old message to 500 characters

ANALYZE_PROMPT = """
You analyze the user's latest message in a conversation with a
document-based enterprise knowledge assistant. Do two things.

1. Classify the intent with exactly one label:

NEW_QUESTION: A new question to answer using the uploaded documents.
FOLLOW_UP: The user wants more details or clarification about a previous
document-related answer.
SEARCH_CLARIFICATION: The user asks what could not be found, why a search
failed, or asks about a previous unsuccessful document search.
SCOPE_QUESTION: The user asks why the assistant cannot answer using general
knowledge, asks about its limitations, or asks for an answer independent of
the uploaded documents.

Intent rules:
- Use the conversation history to understand the user's meaning.
- Prioritize the most recent relevant exchange.
- Short messages can be follow-ups.
- A question that sounds general may still be answerable from documents.
- Do not use SCOPE_QUESTION merely because a general topic like AWS is mentioned.
- Questions about a previous failed search are SEARCH_CLARIFICATION.

2. Rewrite the latest message as one standalone question.

Rewrite rules:
- Use the history to resolve words like "it", "that", "why" and "what didn't you find".
- If the latest message is already clear and standalone, return it unchanged.
- If the assistant could not find information, keep the topic of the original
  unanswered question. Example: after "Tell me how to cook biryani?" and a
  not-found reply, "What didn't you find?" becomes
  "What information about cooking biryani could not be found in the documents?"
- Never replace a specific topic with a generic question.

Do not answer the question or invent information.
"""

ALLOWED_INTENTS = {
    "NEW_QUESTION",
    "FOLLOW_UP",
    "SEARCH_CLARIFICATION",
    "SCOPE_QUESTION",
}


class MessageAnalysis(BaseModel):
    intent: str
    standalone_question: str


def format_transcript(history: list[tuple[str, str]]) -> str:
    """Turn history into short, readable lines: 'role: text'."""
    return "\n".join(
        f"{role}: {content[:MAX_CHARS_PER_MESSAGE]}" for role, content in history
    )


def analyze_message(
    history: list[tuple[str, str]],
    question: str,
) -> tuple[str, str]:
    """One Gemini call that returns (intent, standalone question)."""

    # First message of a chat: nothing to analyze, no call needed.
    if not history:
        return "NEW_QUESTION", question

    prompt = (
        f"Conversation history:\n{format_transcript(history)}\n\n"
        f"Latest user message:\n{question}"
    )

    try:
        result = (
            get_llm()
            .with_structured_output(MessageAnalysis)
            .invoke(
                [
                    SystemMessage(content=ANALYZE_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )
        )

        if result is not None:
            intent = result.intent.strip().upper()
            standalone = result.standalone_question.strip() or question
            if intent in ALLOWED_INTENTS:
                return intent, standalone
            logger.warning("Unexpected intent label: %s", intent)

    except Exception:
        logger.exception("Message analysis failed")

    # If anything fails, search the documents with the original question.
    return "NEW_QUESTION", question