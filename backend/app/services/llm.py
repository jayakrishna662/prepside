from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings

LLM_MODEL = "gemini-3.5-flash-lite"


def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=settings.google_api_key,
    )


def message_text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    ).strip()