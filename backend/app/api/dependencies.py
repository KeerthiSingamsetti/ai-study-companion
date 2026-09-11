"""Shared FastAPI dependency providers for application-composed services."""

from __future__ import annotations

from typing import Any, cast

from fastapi import Request
from langchain_core.language_models.chat_models import BaseChatModel

from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.rag_query_service import RagQueryService
from app.services.thread_service import ThreadService


def get_chat_service(request: Request) -> ChatService:
    """Return the process-scoped chat service composed during application startup."""
    return cast(ChatService, request.app.state.chat_service)


def get_document_service(request: Request) -> DocumentService:
    """Return the process-scoped document service composed during application startup."""
    return cast(DocumentService, request.app.state.document_service)


def get_embeddings(request: Request) -> Any:
    """Return the shared embedding provider composed during application startup."""
    return request.app.state.embeddings


def get_llm(request: Request) -> BaseChatModel:
    """Return the shared chat model composed during application startup."""
    return cast(BaseChatModel, request.app.state.llm)


def get_quiz_llm(request: Request) -> BaseChatModel:
    """Return the dedicated quiz model composed during application startup."""
    return cast(BaseChatModel, request.app.state.quiz_llm)


def get_rag_query_service(request: Request) -> RagQueryService:
    """Return the process-scoped RAG debug service composed during application startup."""
    return cast(RagQueryService, request.app.state.rag_query_service)
def get_thread_service(request: Request) -> ThreadService:
    """Return the process-scoped thread lifecycle service."""
    return cast(
        ThreadService,
        getattr(request.app.state, "thread_service", ThreadService()),
    )
