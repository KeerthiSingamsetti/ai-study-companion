"""FastAPI application composition for StudyMate."""

from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded before any LangChain/LangGraph modules are imported
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env", override=True)

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


from app.agent.checkpointer import close_checkpointer, create_checkpointer
from app.agent.graph import create_graph
from app.agent.llm import create_llm, create_quiz_llm
from app.api.chat import router as chat_router
from app.api.documents import router as document_router
from app.api.rag import router as rag_router
from app.api.routes_flashcards import router as flashcard_router
from app.api.routes_quiz import router as quiz_router
from app.api.routes_planner import router as planner_router
from app.api.routes_progress import router as progress_router
from app.api.threads import router as thread_router
from app.db.session import init_db
from app.rag.embeddings import get_embeddings
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.rag_query_service import RagQueryService
from app.services.thread_service import ThreadService
from app.tools.flashcard_tool import create_flashcard_tool
from app.tools.quiz_generator_tool import create_quiz_tool
from app.tools.rag_tool import create_rag_tool
from app.tools.study_planner_tool import create_study_planner_tool
from app.tools.memory_tool import create_study_progress_tool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and release process-scoped application dependencies."""
    checkpointer = create_checkpointer()
    try:
        init_db()
        embeddings = get_embeddings()
        llm = create_llm()
        quiz_llm = create_quiz_llm()
        app.state.embeddings = embeddings
        app.state.llm = llm
        app.state.quiz_llm = quiz_llm
        app.state.document_service = DocumentService(embeddings)
        app.state.rag_query_service = RagQueryService(embeddings, llm)
        rag_tool = create_rag_tool(embeddings)
        quiz_tool = create_quiz_tool(quiz_llm, embeddings)
        flashcard_tool = create_flashcard_tool(quiz_llm, embeddings)
        planner_tool = create_study_planner_tool(quiz_llm)
        progress_tool = create_study_progress_tool()
        app.state.checkpointer = checkpointer
        app.state.thread_service = ThreadService()
        tools = [rag_tool, quiz_tool, flashcard_tool, planner_tool, progress_tool]
        app.state.chat_service = ChatService(
            create_graph(llm=llm, checkpointer=checkpointer, tools=tools),
            tools=tools,
        )
        yield
    finally:
        close_checkpointer(checkpointer)


def create_app() -> FastAPI:
    """Create the StudyMate FastAPI application."""
    app = FastAPI(title="StudyMate API", lifespan=lifespan)
    app.include_router(chat_router)
    app.include_router(document_router)
    app.include_router(rag_router)
    app.include_router(quiz_router)
    app.include_router(flashcard_router)
    app.include_router(planner_router)
    app.include_router(progress_router)
    app.include_router(thread_router)
    return app


app = create_app()
