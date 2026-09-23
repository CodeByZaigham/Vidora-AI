from langchain_groq import ChatGroq

from config import settings


def get_llm() -> ChatGroq:
    return ChatGroq(
        model=settings.llm_model,
        api_key=settings.mistral_api_key,
    )