"""LLM construction and configuration for the StudyMate chat agent."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def create_llm() -> BaseChatModel:
    """Create the configured Groq chat model.

    Configuration is read from the backend's environment (and its local
    ``.env`` file when present). ``GROQ_API_KEY`` and ``GROQ_MODEL`` must be
    configured by the deployment; no model or credential is embedded here.

    Returns:
        A reusable LangChain chat-model client.

    Raises:
        RuntimeError: If required Groq configuration is absent.
    """
    load_dotenv(_BACKEND_DIR / ".env", override=True)


    api_key = os.getenv("GROQ_API_KEY")
    model_name = os.getenv("GROQ_MODEL")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY must be configured to create the chat model.")
    if not model_name:
        raise RuntimeError("GROQ_MODEL must be configured to create the chat model.")

    # Tool-calling models are more reliable with deterministic sampling.  This
    # is the shared client injected into the LangGraph chatbot, including its
    # tool-bound invocations.
    return ChatGroq(model=model_name, api_key=api_key, temperature=0)


def create_quiz_llm() -> BaseChatModel:
    """Create the dedicated Groq client used only for quiz generation."""
    load_dotenv(_BACKEND_DIR / ".env", override=True)


    api_key = os.getenv("GROQ_QUIZ_API_KEY")
    model_name = os.getenv("GROQ_QUIZ_MODEL") or os.getenv("GROQ_MODEL")
    if not api_key:
        raise RuntimeError("GROQ_QUIZ_API_KEY must be configured to create the quiz model.")
    if not model_name:
        raise RuntimeError("GROQ_MODEL must be configured to create the quiz model.")
    return ChatGroq(model=model_name, api_key=api_key)
