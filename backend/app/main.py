"""FastAPI application composition for StudyMate."""

from __future__ import annotations

import os

# Cap native thread pools BEFORE numpy/faiss/torch get imported. On multi-core
# hosts each BLAS/OpenMP pool reserves per-core buffers that can add hundreds
# of MB of RSS — enough to OOM a 512MB free-tier container during ingestion.
# The web workload is I/O-bound; single-threaded BLAS costs nothing here.
for _var in (
    "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "KMP_INIT_AT_FORK",
):
    os.environ.setdefault(_var, "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import logging
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded before any LangChain/LangGraph modules are imported.
# Existing environment variables win (override=False): the platform owns config
# in deployment, and the test suite must be able to pin DATABASE_URL to its
# disposable database even when a developer's .env points at a hosted Postgres.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env", override=False)

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


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
from app.services.ingestion_worker import (
    get_ingestion_worker,
    recover_pending_ingestion_jobs,
)
from app.services.rag_query_service import RagQueryService
from app.services.thread_service import ThreadService
from app.tools.flashcard_tool import create_flashcard_tool
from app.tools.quiz_generator_tool import create_quiz_tool
from app.tools.rag_tool import create_rag_tool
from app.tools.study_planner_tool import create_study_planner_tool
from app.tools.memory_tool import create_study_progress_tool
from app.tools.recommendation_tool import create_recommendation_tool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and release process-scoped application dependencies."""
    checkpointer = create_checkpointer()
    try:
        init_db()
        # get_embeddings() returns a lazy proxy: the BGE model (and the
        # sentence-transformers/torch stack it needs) is imported and loaded on
        # first real use, not during startup — see app/rag/embeddings.py.
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
        recommendation_tool = create_recommendation_tool()
        app.state.checkpointer = checkpointer
        app.state.thread_service = ThreadService()
        # Single background worker for PDF ingestion. Creating it here pins it
        # to the same embeddings client the rest of the app uses; startup
        # recovery re-enqueues uploads that were still queued when the
        # process last stopped (deploy restarts included). Recovery must
        # never take startup down — a failed requeue is logged, not raised.
        app.state.ingestion_worker = get_ingestion_worker(embeddings)
        try:
            recover_pending_ingestion_jobs()
        except Exception:  # pragma: no cover - defensive
            logging.getLogger(__name__).exception(
                "Startup ingestion recovery failed; continuing without it."
            )
        tools = [rag_tool, quiz_tool, flashcard_tool, planner_tool, progress_tool, recommendation_tool]
        app.state.chat_service = ChatService(
            create_graph(llm=llm, checkpointer=checkpointer, tools=tools),
            tools=tools,
        )
        yield
    finally:
        close_checkpointer(checkpointer)


from app.auth.router import router as auth_router
from app.api.spaces import router as spaces_router
from app.api.analytics import router as analytics_router, admin_router
from app.api.admin import router as admin_console_router
from app.api.learning import router as learning_router


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create the AI Study Companion FastAPI application."""
    app = FastAPI(title="AI Study Companion API", lifespan=lifespan)

    # Every feature router is registered twice:
    #   * at its bare path (/auth/..., /chat/...) — the surface the test suite
    #     targets and the destination of the Vite dev proxy, which forwards
    #     /api/* with the /api prefix stripped; and
    #   * under /api (/api/auth/...) — the base URL the committed production
    #     bundle hard-codes (frontend/src/api/client.js: API_BASE_URL = "/api"),
    #     which must keep working when FastAPI serves that bundle directly.
    for router in (
        auth_router,
        spaces_router,
        chat_router,
        document_router,
        rag_router,
        quiz_router,
        flashcard_router,
        planner_router,
        progress_router,
        thread_router,
        analytics_router,
        admin_router,
        admin_console_router,
        learning_router,
    ):
        app.include_router(router)
        app.include_router(router, prefix="/api")

    _mount_frontend(app)
    return app


# Built SPA committed to the repo so Render (which builds from GitHub, not
# local files) can serve the frontend from the same service as the API.
_FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "static"


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA from backend/static for every non-API path.

    Called last in create_app on purpose: the catch-all route below must be
    registered after all API routes so it can never shadow them. Static
    bundles are served from /assets (Vite's output layout); every other path —
    including / and client-side SPA routes — falls back to index.html so the
    React app boots and routes internally.
    """
    if not (_FRONTEND_DIST_DIR / "index.html").is_file():
        logger.warning(
            "Frontend bundle missing at %s; only the API will be served.",
            _FRONTEND_DIST_DIR,
        )
        return

    assets_dir = _FRONTEND_DIST_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    for filename in ("favicon.svg", "icons.svg"):
        file_path = _FRONTEND_DIST_DIR / filename
        if file_path.is_file():
            app.get("/" + filename, include_in_schema=False)(
                lambda path=file_path: FileResponse(path)
            )

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_frontend(full_path: str = "") -> FileResponse:
        """SPA fallback: serve index.html for any unmatched, non-API path.

        HEAD is included because deployment health probes (Render) use it;
        a 405 here makes the platform treat a perfectly healthy service as
        failing.
        """
        if full_path.startswith("api/"):
            # Unknown API paths must stay machine-readable 404s, not HTML.
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(_FRONTEND_DIST_DIR / "index.html")



app = create_app()
