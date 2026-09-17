"""Shared local HuggingFace embedding provider for StudyMate RAG operations."""

from __future__ import annotations

from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the process-scoped embeddings client used for indexing and retrieval.

    Sentence Transformers downloads BGE automatically on first use and stores
    it in its standard local cache. No NVIDIA credential is required.
    """
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
