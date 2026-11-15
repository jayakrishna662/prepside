# ChatGoogleGenerativeAI is a LangChain class that lets our application communicate with Google's Gemini models.
from langchain_google_genai import ChatGoogleGenerativeAI

# settings gives us access to the application's configuration
from app.core.config import settings

LLM_MODEL = "gemini-3.5-flash-lite"


# creates and returns a Gemini model connection configured with the model name and Google API key.
def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=settings.google_api_key,
    )

# It extracts the text from the message object and returns it as a normal Python string.
# since model gives response message object 
def message_text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    ).strip()