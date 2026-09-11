"""Tests for user-facing citations returned by the RAG debug service."""

from types import SimpleNamespace

from langchain_core.messages import AIMessage

from app.schemas.rag import RagQueryRequest
from app.services.rag_query_service import RagQueryService


class StaticChatModel:
    """Return one deterministic model response without making a network call."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def invoke(self, _messages: object) -> AIMessage:
        """Return the configured answer."""
        return AIMessage(content=self._response_text)


def _chunks() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            content="Unrelated chunk one.",
            source="sample.pdf",
            page=339,
            similarity_score=0.92,
            rerank_score=0.91,
        ),
        SimpleNamespace(
            content="Unrelated chunk two.",
            source="sample.pdf",
            page=341,
            similarity_score=0.84,
            rerank_score=0.82,
        ),
    ]


def test_rag_query_suppresses_sources_but_retains_debug_chunks_for_refusal(monkeypatch) -> None:
    """An unsupported answer exposes no user-facing pages but keeps debug chunks."""
    from app.rag import retriever

    monkeypatch.setattr(retriever, "retrieve", lambda *_args, **_kwargs: _chunks())
    service = RagQueryService(
        embeddings=object(),
        llm=StaticChatModel("The provided context does not contain enough information to answer this question."),
    )

    result = service.query(RagQueryRequest(query="Explain Figure 2-4", index_path="test-index"))

    assert result.sources == []
    assert result.num_chunks == 2
    assert [chunk.page for chunk in result.retrieved_chunks] == [339, 341]


def test_rag_query_returns_sources_when_answer_is_grounded(monkeypatch) -> None:
    """A document-grounded answer receives its deduplicated source citations."""
    from app.rag import retriever

    monkeypatch.setattr(retriever, "retrieve", lambda *_args, **_kwargs: _chunks())
    service = RagQueryService(
        embeddings=object(),
        llm=StaticChatModel("According to sample.pdf, Figure 2-4 shows the relationship described in the context. [[cite:1]]"),
    )

    result = service.query(RagQueryRequest(query="What does the figure show?", index_path="test-index"))

    assert result.answer == "According to sample.pdf, Figure 2-4 shows the relationship described in the context."
    assert [citation.model_dump() for citation in result.sources] == [{"document": "sample.pdf", "page": 339}]


def test_rag_query_deduplicates_explicit_overlapping_evidence(monkeypatch) -> None:
    """Several selected chunks from one page produce one source citation."""
    chunks = _chunks() + [
        SimpleNamespace(
            content="A second overlapping chunk from the same page.",
            source="sample.pdf",
            page=339,
            similarity_score=0.8,
            rerank_score=0.79,
        )
    ]
    from app.rag import retriever

    monkeypatch.setattr(retriever, "retrieve", lambda *_args, **_kwargs: chunks)
    service = RagQueryService(
        embeddings=object(),
        llm=StaticChatModel("The explanation combines both selected passages. [[cite:1]] [[cite:3]] [[cite:2]]"),
    )

    result = service.query(RagQueryRequest(query="Explain the combined concept", index_path="test-index"))

    assert [citation.model_dump() for citation in result.sources] == [
        {"document": "sample.pdf", "page": 339},
        {"document": "sample.pdf", "page": 341},
    ]
