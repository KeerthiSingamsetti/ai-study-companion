"""Figure-caption routing tests for hybrid retrieval."""

from langchain_core.documents import Document

from app.rag.ingest import annotate_figure_metadata
from app.rag import retriever


def _fixture_chunks() -> list[Document]:
    """Build a small corpus where prose mentions create retrieval noise."""
    chunks = [
        Document(
            page_content="Figure 2: The low-number figure caption.",
            metadata={"source": "fixture.pdf", "page": 2, "chunk_id": "caption-2"},
        ),
        Document(
            page_content="Figure 3: The next figure caption.",
            metadata={"source": "fixture.pdf", "page": 3, "chunk_id": "caption-3"},
        ),
        Document(
            page_content="Figure 2-40: The high-number figure caption.",
            metadata={"source": "fixture.pdf", "page": 40, "chunk_id": "caption-40"},
        ),
        Document(
            page_content="The chapter body mentions Figure 2 many times without explaining it.",
            metadata={"source": "fixture.pdf", "page": 20, "chunk_id": "body-2"},
        ),
    ]
    annotate_figure_metadata(chunks)
    return chunks


def test_figure_metadata_distinguishes_caption_and_body_mentions() -> None:
    """Ingestion gives captions priority metadata without losing body references."""
    caption, _, _, body = _fixture_chunks()

    assert caption.metadata["is_caption"] is True
    assert caption.metadata["figure_number"] == 2
    assert body.metadata["is_caption"] is False
    assert body.metadata["figure_number"] == 2
    assert body.metadata["figure_numbers"] == [2]


def test_explicit_figure_queries_rank_matching_captions_first(monkeypatch) -> None:
    """Caption chunks outrank noisy prose for low and high explicit figure numbers."""
    chunks = _fixture_chunks()
    noisy_order = [
        (chunks[3], 1.0),
        (chunks[1], 0.9),
        (chunks[2], 0.8),
        (chunks[0], 0.7),
    ]

    monkeypatch.setattr(retriever.store, "load_index", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(retriever.store, "load_chunks", lambda _path: chunks)
    monkeypatch.setattr(retriever.store, "index_fingerprint", lambda _path: "fixture-index")
    monkeypatch.setattr(
        retriever,
        "_hybrid_candidates",
        lambda *_args, **_kwargs: noisy_order,
    )

    expected_caption_ids = {
        "what was fig 2 about": "caption-2",
        "Explain Figure 3": "caption-3",
        "What does fig 40 show?": "caption-40",
    }
    for query, expected_chunk_id in expected_caption_ids.items():
        results = retriever.retrieve(
            query,
            "fixture-index",
            embeddings=object(),
            use_hybrid_search=True,
            use_reranking=False,
            k=3,
            cache_results=False,
        )

        assert results[0].metadata["chunk_id"] == expected_chunk_id
        assert results[0].score_type == "figure_caption_exact_match"
