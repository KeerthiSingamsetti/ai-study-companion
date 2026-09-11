"""Tool wrapper that exposes the existing StudyMate RAG retriever to LangGraph."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
import logging

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

from app.db import crud
from app.db.session import SessionLocal
from app.rag.exceptions import DocumentNotIndexedError
from app.rag.retriever import retrieve

if TYPE_CHECKING:
    from app.rag.retriever import RetrievedChunk

VectorstorePathResolver = Callable[[str], list[str]]


def get_vectorstore_paths_for_thread(thread_id: str) -> list[str]:
    """Return persisted vector-store paths belonging to one StudyMate thread."""
    db = SessionLocal()
    try:
        return [
            document.vectorstore_path
            for document in crud.list_documents_for_thread(db, thread_id)
        ]
    finally:
        db.close()


def _format_context(chunks: list["RetrievedChunk"], max_total_chars: int = 6000) -> str:
    """Format retrieved chunks with stable source citations for the model.

    ``max_total_chars`` caps the total context length so large PDFs cannot
    push requests over Groq's free-tier token limit.
    """
    if not chunks:
        return (
            "No relevant uploaded-document context was found. State this clearly "
            "and do not invent document-based facts."
        )

    sections = []
    total_chars = 0
    for number, chunk in enumerate(chunks, start=1):
        source_name = Path(chunk.source).name if chunk.source else "document"
        page = f", page {chunk.page + 1}" if chunk.page is not None else ""
        # Truncate individual chunks to avoid a single monster chunk blowing the limit
        content = chunk.content[:1500] if len(chunk.content) > 1500 else chunk.content
        entry = f"[SOURCE:{number}] {source_name}{page}\n{content}"
        if total_chars + len(entry) > max_total_chars:
            break
        sections.append(entry)
        total_chars += len(entry)
    return "Retrieved uploaded-document context:\n\n" + "\n\n".join(sections)


def _build_citation_artifacts(chunks: list["RetrievedChunk"]) -> list[dict[str, Any]]:
    """Build source-ID metadata; response services deduplicate selected pages."""
    citations: list[dict[str, Any]] = []

    for citation_id, chunk in enumerate(chunks, start=1):
        doc_name = Path(chunk.source).name if chunk.source else "document"
        page_num = chunk.page + 1 if chunk.page is not None else None
        citations.append(
            {"citation_id": citation_id, "document": doc_name, "page": page_num}
        )
    return citations


def create_rag_tool(
    embeddings: Any,
    *,
    vectorstore_path_resolver: VectorstorePathResolver = get_vectorstore_paths_for_thread,
) -> BaseTool:
    """Create a tool that retrieves context from documents in the active thread.

    LangChain injects invocation configuration, keeping ``thread_id`` out of
    the model-visible tool schema.
    """

    @tool
    def search_uploaded_documents(query: str, config: RunnableConfig) -> str:
        """Search this conversation's uploaded PDF documents for facts needed to answer a question about uploaded study material."""
        logger.info(
            "ToolNode executing search_uploaded_documents with query=%r", query
        )
        thread_id = config.get("configurable", {}).get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            logger.warning("No thread_id available for document retrieval.")
            return "No conversation identity is available for document retrieval."

        paths = vectorstore_path_resolver(thread_id)
        if not paths:
            logger.info("No vectorstore paths found for this thread.")
            return "No uploaded documents are available in this conversation."

        chunks: list[Any] = []

        for path in paths:
            try:
                chunks.extend(retrieve(
                    query,
                    path,
                    embeddings,
                    use_hybrid_search=True,
                    k=8,           # reduced from 15 to save tokens
                    rerank_top_k=4, # reduced from 6 to save tokens
                ))
            except DocumentNotIndexedError:
                continue

        chunks.sort(key=lambda chunk: chunk.relevance_score or 0.0, reverse=True)
        context = _format_context(chunks)
        logger.info(
            "ToolNode completed search_uploaded_documents: retrieved_chunks=%d",
            len(chunks),
        )
        return context

    return search_uploaded_documents
