"""Application service for debugging the existing StudyMate RAG pipeline."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pathlib import Path

from app.schemas.chat import DocumentCitation
from app.schemas.rag import RagQueryRequest, RagQueryResponse, RetrievedChunkResponse
from app.services.citations import (
    extract_citation_ids,
    is_grounded_refusal,
    strip_citation_markers,
)

GROUNDED_RAG_PROMPT = """You are StudyMate, an AI study assistant.

Answer using ONLY the provided context. If the context does not contain enough
information, say: "The provided context does not contain enough information to
answer this question." Verify that chunks concern the same topic as the
question, do not combine unrelated chunks, and answer clearly and concisely.
Each context passage is labelled [SOURCE:n]. Mark each directly used passage
with [[cite:n]], using the minimum number of markers necessary. Do not mark
irrelevant passages. Do not use markers when refusing the question."""


class NoRelevantChunksError(LookupError):
    """Raised when an existing index returns no relevant source chunks."""


def build_context_block(chunks: list[Any]) -> str:
    """Format retrieved chunks using the existing manual-test context convention."""
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        score_details = f"similarity: {chunk.similarity_score:.3f}"
        if chunk.rerank_score is not None:
            score_details += f", rerank: {chunk.rerank_score:.3f}"
        parts.append(
            f"[SOURCE:{index}] (source: {chunk.source}, page: {chunk.page}, {score_details})\n"
            f"{chunk.content}"
        )
    return "\n\n".join(parts)


def extract_chunk_citations(
    chunks: list[Any], answer_text: str
) -> list[DocumentCitation]:
    """Build citations only for retrieved chunks explicitly selected as evidence."""
    if is_grounded_refusal(answer_text):
        return []

    selected_ids = extract_citation_ids(answer_text)
    if not selected_ids:
        return []

    seen: set[tuple[str, int | None]] = set()
    citations: list[DocumentCitation] = []
    for citation_id in selected_ids:
        if citation_id < 1 or citation_id > len(chunks):
            continue
        chunk = chunks[citation_id - 1]
        doc_name = Path(str(chunk.source)).name
        page_val: int | None = int(chunk.page) if isinstance(chunk.page, int) else None
        key = (doc_name, page_val)
        if key not in seen:
            seen.add(key)
            citations.append(DocumentCitation(document=doc_name, page=page_val))
    return citations


class RagQueryService:
    """Invoke the established retriever and generate a grounded debug answer."""

    def __init__(self, embeddings: Any, llm: BaseChatModel) -> None:
        self._embeddings = embeddings
        self._llm = llm

    def query(self, request: RagQueryRequest) -> RagQueryResponse:
        """Query an existing index without rebuilding or altering it."""
        from app.rag.retriever import retrieve

        chunks = retrieve(
            request.query,
            request.index_path,
            self._embeddings,
            use_reranking=request.use_reranking,
            use_hybrid_search=request.use_hybrid_search,
            k=request.k,
            rerank_top_k=request.rerank_top_k,
        )
        if not chunks:
            raise NoRelevantChunksError("No relevant chunks were retrieved.")

        response = self._llm.invoke([
            SystemMessage(content=GROUNDED_RAG_PROMPT),
            HumanMessage(content=f"Context:\n{build_context_block(chunks)}\n\nQuestion: {request.query}"),
        ])
        answer_text: str = response.text
        sources = extract_chunk_citations(chunks, answer_text)
        return RagQueryResponse(
            answer=strip_citation_markers(answer_text),
            num_chunks=len(chunks),
            sources=sources,
            retrieved_chunks=[
                RetrievedChunkResponse(
                    content=chunk.content,
                    source=chunk.source,
                    page=chunk.page,
                    similarity_score=chunk.similarity_score,
                    rerank_score=chunk.rerank_score,
                )
                for chunk in chunks
            ],
        )
