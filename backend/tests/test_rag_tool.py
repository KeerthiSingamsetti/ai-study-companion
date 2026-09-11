"""Focused tests for the LangGraph RAG tool wrapper."""

from app.rag.retriever import RetrievedChunk
from app.tools.rag_tool import create_rag_tool


def test_rag_tool_uses_existing_retriever_for_active_thread(monkeypatch) -> None:
    """A document search resolves the active thread and formats retrieved context."""
    calls: list[tuple[str, str, object]] = []

    def fake_retrieve(query: str, path: str, embeddings: object, **_kwargs: object):
        calls.append((query, path, embeddings))
        return [
            RetrievedChunk(
                content="Mitochondria produce ATP.",
                source="biology.pdf",
                page=2,
                similarity_score=0.9,
                relevance_score=0.9,
            )
        ]

    monkeypatch.setattr("app.tools.rag_tool.retrieve", fake_retrieve)
    embeddings = object()
    rag_tool = create_rag_tool(
        embeddings, vectorstore_path_resolver=lambda thread_id: ["index-path"]
    )

    result = rag_tool.invoke(
        {"query": "Where is ATP produced?"},
        config={"configurable": {"thread_id": "thread-1"}},
    )

    assert calls == [("Where is ATP produced?", "index-path", embeddings)]
    assert "biology.pdf, page 3" in result
    assert "Mitochondria produce ATP." in result


def test_rag_tool_reports_missing_documents_without_retrieval() -> None:
    """No document paths produces an honest non-grounded tool result."""
    rag_tool = create_rag_tool(
        object(), vectorstore_path_resolver=lambda thread_id: []
    )

    result = rag_tool.invoke(
        {"query": "What is in my PDF?"},
        config={"configurable": {"thread_id": "thread-1"}},
    )

    assert result == "No uploaded documents are available in this conversation."
