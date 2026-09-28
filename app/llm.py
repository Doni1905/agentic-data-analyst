"""LLM factory: Gemini free tier by default, Groq as the alternative.

Keys come from .env (see .env.example) - never hardcoded.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def build_llm() -> BaseChatModel:
    provider = settings.llm_provider
    if provider == "gemini":
        if not settings.google_api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is missing. Add it to .env "
                "(free key: https://aistudio.google.com/app/apikey)"
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0,
        )
    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Add it to .env "
                "(free key: https://console.groq.com/keys)"
            )
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=0,
        )
    raise RuntimeError(f"Unknown LLM_PROVIDER '{provider}' - use 'gemini' or 'groq'.")
