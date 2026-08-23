from langchain_mistralai import ChatMistralAI

from config import settings


def get_llm() -> ChatMistralAI:
    return ChatMistralAI(
        model=settings.llm_model,
        api_key=settings.mistral_api_key,
    )