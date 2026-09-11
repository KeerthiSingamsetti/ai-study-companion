"""High-quality, metadata-aware retrieval for the StudyMate RAG pipeline.

The public ``retrieve`` API remains compatible with the original dense/hybrid
pipeline while adding optional multi-query union, metadata filtering/boosting,
calibrated thresholding, context compression, and an in-process cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from app.rag import store
from app.rag.exceptions import DocumentNotIndexedError, VectorStoreLoadError
from app.rag.reranker import MODEL_NAME as RERANKER_MODEL_NAME
from app.rag.reranker import rerank

logger = logging.getLogger(__name__)

_RETRIEVAL_CACHE_MAX_SIZE = 256
_RETRIEVAL_CACHE: OrderedDict[str, Tuple["RetrievedChunk", ...]] = OrderedDict()
_RETRIEVAL_CACHE_LOCK = threading.Lock()
_BM25_CACHE: dict[tuple[str, str, str], BM25Retriever] = {}
_BM25_CACHE_LOCK = threading.Lock()
_FIGURE_REFERENCE_PATTERN = re.compile(
    # Captures the full label including optional chapter prefix, e.g. "7-1" or just "1"
    r"\bfig(?:ure)?\.?\s*((?:\d+\s*-\s*)?\d+)(?=[:.\s?]|$)",
    re.IGNORECASE,
)


class RetrievedChunk(BaseModel):
    """A retrieved document plus scores and stable provenance metadata.

    ``similarity_score`` remains backwards compatible: dense retrieval exposes
    ``1 / (1 + L2_distance)`` and hybrid retrieval exposes normalized RRF.
    ``rerank_score`` is the raw cross-encoder logit.  ``relevance_score`` is
    a bounded 0--1 score suitable for thresholds; for reranked results it is
    sigmoid(raw cross-encoder logit), not the raw score itself.
    """

    content: str
    source: str
    page: Optional[int] = None
    similarity_score: float
    rerank_score: Optional[float] = None
    relevance_score: Optional[float] = None
    score_type: str = "dense_l2_similarity"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_content: Optional[str] = None
    compressed: bool = False


def clear_retrieval_cache(save_path: Optional[str] = None) -> None:
    """Clear cached results and the paired BM25 indexes.

    ``store.build_and_save_index`` and ``store.delete_index`` naturally change
    the index fingerprint, but this hook is useful for explicit invalidation.
    """
    with _RETRIEVAL_CACHE_LOCK:
        if save_path is None:
            _RETRIEVAL_CACHE.clear()
        else:
            # Cache keys are hashes; clearing all is safer than retaining a
            # possibly stale opaque key for a rebuilt index.
            _RETRIEVAL_CACHE.clear()
    with _BM25_CACHE_LOCK:
        if save_path is None:
            _BM25_CACHE.clear()
        else:
            resolved = str(__import__("pathlib").Path(save_path).resolve())
            for key in list(_BM25_CACHE):
                if key[0] == resolved:
                    _BM25_CACHE.pop(key, None)


def _document_key(document: Document) -> str:
    """Stable key that avoids object-identity bugs after filtering/copying."""
    metadata = document.metadata or {}
    chunk_id = metadata.get("chunk_id")
    if chunk_id:
        return f"chunk:{chunk_id}"
    raw = "|".join((
        str(metadata.get("source", "")),
        str(metadata.get("page", "")),
        document.page_content,
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _matches_one(value: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        if "$in" in expected and value not in expected["$in"]:
            return False
        if "$nin" in expected and value in expected["$nin"]:
            return False
        if "$gte" in expected and (value is None or value < expected["$gte"]):
            return False
        if "$gt" in expected and (value is None or value <= expected["$gt"]):
            return False
        if "$lte" in expected and (value is None or value > expected["$lte"]):
            return False
        if "$lt" in expected and (value is None or value >= expected["$lt"]):
            return False
        if "$eq" in expected and value != expected["$eq"]:
            return False
        return True
    if isinstance(expected, (list, tuple, set, frozenset)):
        return value in expected
    return value == expected


def _matches_metadata(document: Document, metadata_filter: Optional[Mapping[str, Any]]) -> bool:
    if not metadata_filter:
        return True
    metadata = document.metadata or {}
    return all(_matches_one(metadata.get(key), expected)
               for key, expected in metadata_filter.items())


def _metadata_boost(document: Document, preferences: Optional[Mapping[str, Any]], weight: float) -> float:
    if not preferences or weight <= 0:
        return 0.0
    return weight if _matches_metadata(document, preferences) else 0.0


def _figure_label_from_query(query: str) -> Optional[str]:
    """Return the full figure label from query (e.g. '7-1' or '3'), or None."""
    match = _FIGURE_REFERENCE_PATTERN.search(query)
    if not match:
        return None
    # Normalise whitespace around the dash so '7 - 1' → '7-1'
    return re.sub(r"\s*-\s*", "-", match.group(1).strip())


# Keep the old name as an alias for backwards compat with any test imports.
def _figure_number_from_query(query: str) -> Optional[int]:
    """Return the trailing integer from a figure label in *query*, or None."""
    label = _figure_label_from_query(query)
    if label is None:
        return None
    # e.g. '7-1' → 1,  '3' → 3
    return int(label.split("-")[-1])


def _figure_caption_documents(save_path: str, figure_number: int) -> List[Document]:
    """Load exact caption chunks for a figure before normal hybrid retrieval."""
    return _figure_label_documents(save_path, str(figure_number), figure_number)


def _figure_label_documents(
    save_path: str, full_label: str, trailing_number: int
) -> List[Document]:
    """Return chunks that reference *full_label* exactly (e.g. '7-1').

    Strategy
    --------
    - Always scan chunk text for the **exact full label** (e.g. "Figure 7-1").
      This is the only reliable match for hyphenated labels.
    - For simple (non-hyphenated) labels such as "3", also allow a
      metadata-number fallback so plain "Figure 3" queries still work.
    - **Never** fall back to trailing-number matching for hyphenated labels
      (e.g. trailing number of "7-1" is 1, which would wrongly return
      Figure 1-1, Figure 2-1, Figure 3-1 …).
    - Return empty list when the figure is not found — the LLM will then
      correctly report that it couldn't find the figure.
    """
    try:
        chunks = store.load_chunks(save_path)
    except VectorStoreLoadError:
        logger.warning("Could not inspect figure metadata for %s", save_path)
        return []

    if not chunks:
        return []

    is_hyphenated = "-" in full_label

    # Build a pattern that matches the full label, tolerating spacing around dashes
    label_escaped = re.escape(full_label).replace(r"\-", r"\s*-\s*")
    label_pattern = re.compile(
        r"\bfig(?:ure)?\.?\s*" + label_escaped + r"(?=[:.?\s]|$)",
        re.IGNORECASE,
    )

    # Also match the stored figure_label metadata (set by ingest.py for new uploads)
    exact_label_hits: list[Document] = []
    number_only_hits: list[Document] = []

    for chunk in chunks:
        meta = chunk.metadata or {}

        # Check stored figure_label metadata first (precise, set during ingest)
        stored_label: str = meta.get("figure_label", "")
        if stored_label and stored_label == full_label:
            exact_label_hits.append(chunk)
            continue

        # Fallback: scan the raw text for the full label pattern
        if label_pattern.search(chunk.page_content):
            exact_label_hits.append(chunk)
            continue

        # For simple (non-hyphenated) labels only: allow number-metadata fallback
        if not is_hyphenated:
            fig_num = meta.get("figure_number")
            if fig_num == trailing_number or trailing_number in (meta.get("figure_numbers") or []):
                number_only_hits.append(chunk)

    if exact_label_hits:
        return exact_label_hits

    # Only use number fallback for simple labels (e.g. "Figure 3", not "Figure 7-1")
    if not is_hyphenated and number_only_hits:
        return number_only_hits

    # Figure not found in document — return empty so the LLM reports "not found"
    logger.info(
        "_figure_label_documents: no chunks found for label=%r in %s", full_label, save_path
    )
    return []



def _sigmoid(value: float) -> float:
    # Numerically stable for raw cross-encoder logits.
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _cache_key(
    *,
    query: str,
    query_variants: Sequence[str],
    save_path: str,
    use_reranking: bool,
    use_hybrid_search: bool,
    k: int,
    rerank_top_k: int,
    bm25_weight: float,
    dense_weight: float,
    metadata_filter: Optional[Mapping[str, Any]],
    metadata_preferences: Optional[Mapping[str, Any]],
    metadata_boost_weight: float,
    min_similarity: Optional[float],
    min_relevance_score: Optional[float],
) -> str:
    payload = {
        "query": query,
        "query_variants": list(query_variants),
        "index_fingerprint": store.index_fingerprint(save_path),
        "use_reranking": use_reranking,
        "reranker_model": RERANKER_MODEL_NAME if use_reranking else None,
        "use_hybrid_search": use_hybrid_search,
        "k": k,
        "rerank_top_k": rerank_top_k,
        "bm25_weight": bm25_weight,
        "dense_weight": dense_weight,
        "metadata_filter": metadata_filter,
        "metadata_preferences": metadata_preferences,
        "metadata_boost_weight": metadata_boost_weight,
        "min_similarity": min_similarity,
        "min_relevance_score": min_relevance_score,
    }
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _cached_results(key: str) -> Optional[List[RetrievedChunk]]:
    with _RETRIEVAL_CACHE_LOCK:
        cached = _RETRIEVAL_CACHE.get(key)
        if cached is None:
            return None
        _RETRIEVAL_CACHE.move_to_end(key)
        return [chunk.model_copy(deep=True) for chunk in cached]


def _save_cached_results(key: str, results: Sequence[RetrievedChunk]) -> None:
    with _RETRIEVAL_CACHE_LOCK:
        _RETRIEVAL_CACHE[key] = tuple(chunk.model_copy(deep=True) for chunk in results)
        _RETRIEVAL_CACHE.move_to_end(key)
        while len(_RETRIEVAL_CACHE) > _RETRIEVAL_CACHE_MAX_SIZE:
            _RETRIEVAL_CACHE.popitem(last=False)


def _dense_candidates(
    query: str,
    vectorstore: Any,
    candidate_k: int,
    metadata_filter: Optional[Mapping[str, Any]],
) -> List[Tuple[Document, float]]:
    raw_results = vectorstore.similarity_search_with_score(query, k=candidate_k)
    return [
        (document, float(1 / (1 + distance)))
        for document, distance in raw_results
        if _matches_metadata(document, metadata_filter)
    ]


def _bm25_for(
    save_path: str,
    metadata_filter: Optional[Mapping[str, Any]],
) -> BM25Retriever:
    try:
        chunks = store.load_chunks(save_path)
    except VectorStoreLoadError as error:
        raise DocumentNotIndexedError(
            f"Could not load chunks for hybrid search at {save_path}"
        ) from error
    if not chunks:
        raise DocumentNotIndexedError(
            f"Hybrid search requires chunks.pkl at {save_path}; rebuild the index."
        )

    filtered = [chunk for chunk in chunks if _matches_metadata(chunk, metadata_filter)]
    if not filtered:
        # BM25Retriever cannot represent an empty corpus. The caller will use
        # this sentinel-free result path and return no retrieved chunks.
        return None  # type: ignore[return-value]

    filter_key = json.dumps(metadata_filter or {}, sort_keys=True, default=str)
    key = (str(__import__("pathlib").Path(save_path).resolve()), store.index_fingerprint(save_path), filter_key)
    with _BM25_CACHE_LOCK:
        cached = _BM25_CACHE.get(key)
        if cached is not None:
            return cached
    retriever = BM25Retriever.from_documents(filtered)
    with _BM25_CACHE_LOCK:
        _BM25_CACHE[key] = retriever
    return retriever


def _hybrid_candidates(
    query: str,
    vectorstore: Any,
    save_path: str,
    candidate_k: int,
    bm25_weight: float,
    dense_weight: float,
    metadata_filter: Optional[Mapping[str, Any]],
) -> List[Tuple[Document, float]]:
    """Metadata-aware reciprocal-rank fusion without rebuilding BM25 per query."""
    bm25 = _bm25_for(save_path, metadata_filter)
    if bm25 is None:
        return []
    bm25.k = candidate_k
    bm25_docs = bm25.invoke(query)
    dense = _dense_candidates(query, vectorstore, candidate_k, metadata_filter)

    fused: dict[str, list[Any]] = {}
    rrf_constant = 60
    for weight, ranked_documents in (
        (bm25_weight, bm25_docs),
        (dense_weight, [document for document, _ in dense]),
    ):
        for rank, document in enumerate(ranked_documents, start=1):
            key = _document_key(document)
            if key not in fused:
                fused[key] = [document, 0.0]
            fused[key][1] += weight / (rrf_constant + rank)

    if not fused:
        return []
    maximum = max(score for _, score in fused.values())
    ranked = [(document, float(score / maximum)) for document, score in fused.values()]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked[:candidate_k]


def _as_retrieved(document: Document, score: float, score_type: str) -> RetrievedChunk:
    metadata = dict(document.metadata or {})
    return RetrievedChunk(
        content=document.page_content,
        source=str(metadata.get("source", "Unknown")),
        page=metadata.get("page"),
        similarity_score=float(score),
        rerank_score=None,
        relevance_score=float(score),
        score_type=score_type,
        metadata=metadata,
    )


def retrieve(
    query: str,
    save_path: str,
    embeddings: Any,
    use_reranking: bool = True,
    use_hybrid_search: bool = False,
    k: int = 6,
    rerank_top_k: int = 4,
    bm25_weight: float = 0.4,
    dense_weight: float = 0.6,
    *,
    query_variants: Optional[Sequence[str]] = None,
    metadata_filter: Optional[Mapping[str, Any]] = None,
    metadata_preferences: Optional[Mapping[str, Any]] = None,
    metadata_boost_weight: float = 0.05,
    min_similarity: Optional[float] = None,
    min_relevance_score: Optional[float] = None,
    cache_results: bool = True,
) -> List[RetrievedChunk]:
    """Retrieve grounded chunks with optional quality and speed controls.

    ``query_variants`` must be generated by the caller. Candidates from all
    variants are deduplicated by stable chunk ID and reranked exactly once
    against the original query, avoiding incomparable cross-query rerank
    scores. ``metadata_filter`` supports exact values, collections, and
    ``$in/$nin/$gt/$gte/$lt/$lte/$eq`` operations.

    Thresholds use bounded scores: ``min_similarity`` acts before reranking
    on dense/RRF candidates, while ``min_relevance_score`` acts afterwards on
    ``relevance_score`` (sigmoid of the cross-encoder logit when reranked).
    An empty result is valid and intentionally enables grounded refusal.
    """
    if not query.strip():
        return []
    if k <= 0 or rerank_top_k <= 0:
        raise ValueError("k and rerank_top_k must be positive integers.")
    if use_hybrid_search and (bm25_weight < 0 or dense_weight < 0 or bm25_weight + dense_weight == 0):
        raise ValueError("Hybrid retrieval weights must be non-negative and not both zero.")

    variants = [query]
    for variant in query_variants or ():
        if isinstance(variant, str) and variant.strip() and variant.strip() not in variants:
            variants.append(variant.strip())

    try:
        vectorstore = store.load_index(save_path, embeddings)
    except VectorStoreLoadError as error:
        raise DocumentNotIndexedError(
            f"Index exists but is corrupted, incompatible, or unreadable at {save_path}"
        ) from error
    if vectorstore is None:
        raise DocumentNotIndexedError(f"No index exists at {save_path}")

    # ── Figure pre-injection ─────────────────────────────────────────────────
    figure_label = _figure_label_from_query(query)     # e.g. '7-1' or None
    figure_number = _figure_number_from_query(query)  # trailing int, e.g. 1
    figure_captions: List[Document] = []

    if figure_label is not None and figure_number is not None:
        figure_captions = _figure_label_documents(save_path, figure_label, figure_number)
        # Inject an exact-label query variant so BM25 also targets body chunks
        # that mention e.g. "Figure 7-1" even without a tagged caption chunk.
        label_variant = f"Figure {figure_label}"
        if label_variant not in variants:
            variants.append(label_variant)

    key = _cache_key(
        query=query,
        query_variants=variants,
        save_path=save_path,
        use_reranking=use_reranking,
        use_hybrid_search=use_hybrid_search,
        k=k,
        rerank_top_k=rerank_top_k,
        bm25_weight=bm25_weight,
        dense_weight=dense_weight,
        metadata_filter=metadata_filter,
        metadata_preferences=metadata_preferences,
        metadata_boost_weight=metadata_boost_weight,
        min_similarity=min_similarity,
        min_relevance_score=min_relevance_score,
    )
    if cache_results:
        cached = _cached_results(key)
        if cached is not None:
            return cached

    candidate_k = max(k * 2, rerank_top_k * 2)
    merged: dict[str, Tuple[Document, float]] = {}
    for variant in variants:
        if use_hybrid_search:
            candidates = _hybrid_candidates(
                variant, vectorstore, save_path, candidate_k, bm25_weight,
                dense_weight, metadata_filter,
            )
            score_type = "hybrid_rrf_relevance"
        else:
            candidates = _dense_candidates(variant, vectorstore, candidate_k, metadata_filter)
            score_type = "dense_l2_similarity"
        for document, score in candidates:
            if min_similarity is not None and score < min_similarity:
                continue
            document_key = _document_key(document)
            previous = merged.get(document_key)
            if previous is None or score > previous[1]:
                merged[document_key] = (document, score)

    candidate_pairs = sorted(merged.values(), key=lambda pair: pair[1], reverse=True)
    if not candidate_pairs:
        if cache_results:
            _save_cached_results(key, [])
        return []

    if not use_reranking:
        results = []
        for document, score in candidate_pairs:
            boost = _metadata_boost(document, metadata_preferences, metadata_boost_weight)
            result = _as_retrieved(document, min(1.0, score + boost), score_type)
            result.similarity_score = float(score)
            if min_relevance_score is None or result.relevance_score >= min_relevance_score:
                results.append(result)
        results.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
        results = results[:k]
    else:
        documents = [document for document, _ in candidate_pairs]
        base_scores = {_document_key(document): score for document, score in candidate_pairs}
        reranked = rerank(query, documents, top_k=len(documents))
        results = []
        for document, raw_rerank_score in reranked:
            relevance = min(1.0, _sigmoid(float(raw_rerank_score)) + _metadata_boost(
                document, metadata_preferences, metadata_boost_weight
            ))
            if min_relevance_score is not None and relevance < min_relevance_score:
                continue
            result = _as_retrieved(document, base_scores[_document_key(document)], "reranker_sigmoid")
            result.rerank_score = float(raw_rerank_score)
            result.relevance_score = relevance
            results.append(result)
        results.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
        results = results[:rerank_top_k]

    if figure_captions:
        result_limit = rerank_top_k if use_reranking else k
        caption_results = [
            _as_retrieved(document, 1.0, "figure_caption_exact_match")
            for document in figure_captions
        ]
        for caption in caption_results:
            caption.relevance_score = 1.0

        caption_keys = {
            _document_key(document) for document in figure_captions
        }
        fallback_results = [
            result
            for result in results
            if _document_key(
                Document(page_content=result.content, metadata=result.metadata)
            ) not in caption_keys
        ]
        results = (caption_results + fallback_results)[:result_limit]

    if cache_results:
        _save_cached_results(key, results)
    return results


def _split_sentences(text: str) -> List[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text.strip()) if sentence.strip()]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return numerator / (left_norm * right_norm + 1e-12)


def compress_retrieved_chunks(
    chunks: Sequence[RetrievedChunk],
    query: str,
    embeddings: Any,
    *,
    max_sentences: int = 3,
    max_chars: int = 400,
) -> List[RetrievedChunk]:
    """Return semantically compressed copies while preserving provenance.

    The compressed ``content`` is exactly what callers should send to both the
    generator and RAGAS, while ``raw_content`` retains the original chunk for
    debugging and auditability.
    """
    if not chunks or max_sentences <= 0 or max_chars <= 0:
        return [] if not chunks else [chunk.model_copy(deep=True) for chunk in chunks]
    query_embedding = embeddings.embed_query(query)
    compressed_chunks: List[RetrievedChunk] = []
    for chunk in chunks:
        sentences = _split_sentences(chunk.content)
        if len(sentences) <= max_sentences:
            compressed = chunk.content[:max_chars]
        else:
            sentence_embeddings = embeddings.embed_documents(sentences)
            selected = sorted(
                sorted(
                    range(len(sentences)),
                    key=lambda index: _cosine(query_embedding, sentence_embeddings[index]),
                    reverse=True,
                )[:max_sentences]
            )
            compressed = " ".join(sentences[index] for index in selected)[:max_chars]
        metadata = dict(chunk.metadata)
        metadata["compression"] = {
            "max_sentences": max_sentences,
            "max_chars": max_chars,
            "original_chars": len(chunk.content),
        }
        compressed_chunks.append(chunk.model_copy(update={
            "content": compressed,
            "raw_content": chunk.raw_content or chunk.content,
            "compressed": compressed != chunk.content,
            "metadata": metadata,
        }))
    return compressed_chunks
