"""Embedding provider for StudyMate RAG operations.

Embeddings come from Cohere's hosted embed API instead of a local
sentence-transformers model: a small Render container cannot fit torch plus
model weights (the previous local BGE encoder measured ~650MB resident on top
of a 512MB limit), while an HTTP call costs no resident model memory.

``langchain_huggingface`` / ``sentence_transformers`` (and therefore torch)
are no longer imported anywhere in the application import graph.

The Cohere call is made with ``requests`` (declared in requirements.txt), not
the heavier ``cohere`` SDK. Documents are embedded with
``input_type="search_document"`` and queries with ``input_type="search_query"``:
Cohere v3 embed models are trained around that distinction and retrieval
quality degrades badly when the two are mixed.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, List

import requests
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

COHERE_EMBED_MODEL = os.getenv("COHERE_EMBED_MODEL", "embed-english-v3.0")
COHERE_API_BASE = "https://api.cohere.com/v2/embed"
# Cohere's embed endpoint accepts up to 96 texts per request; stay below it.
COHERE_BATCH_SIZE = 96
COHERE_REQUEST_TIMEOUT_SECONDS = 30.0

_EMBEDDINGS: Any = None
_EMBEDDINGS_LOCK = threading.Lock()


class EmbeddingAPIError(RuntimeError):
    """Raised when the Cohere embed API is unreachable, misconfigured, or fails."""


class CohereEmbeddings(Embeddings):
    """Minimal requests-based Cohere embed client.

    Subclasses LangChain's ``Embeddings`` ABC — FAISS and other LangChain
    vector stores hard-validate ``isinstance(x, Embeddings)`` and fall back to
    calling the object directly otherwise, which is exactly what broke
    retrieval while this was a plain duck-typed class. ``model_name`` mirrors
    the flat attribute the index-provenance layer records, keeping existing
    indexes compatible with the identity check in
    ``app.rag.store.embedding_identifier``.
    """

    def __init__(
        self,
        api_key: str,
        model: str = COHERE_EMBED_MODEL,
        timeout: float = COHERE_REQUEST_TIMEOUT_SECONDS,
        api_base: str = COHERE_API_BASE,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._api_base = api_base
        # Flat public attribute: index provenance reads it without touching
        # the network (and without triggering any lazy client build).
        self.model_name = model

    def _embed(self, texts: List[str], input_type: str) -> List[List[float]]:
        vectors: List[List[float]] = []
        for start in range(0, len(texts), COHERE_BATCH_SIZE):
            batch = texts[start : start + COHERE_BATCH_SIZE]
            try:
                response = requests.post(
                    self._api_base,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "texts": batch,
                        "embedding_types": ["float"],
                        "input_type": input_type,
                    },
                    timeout=self._timeout,
                )
            except requests.RequestException as error:
                raise EmbeddingAPIError(f"Cohere embed request failed: {error}") from error
            if response.status_code != 200:
                raise EmbeddingAPIError(
                    f"Cohere embed API returned HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
            try:
                embeddings = response.json()["embeddings"]["float"]
            except (KeyError, TypeError, ValueError) as error:
                raise EmbeddingAPIError(
                    "Cohere embed API returned an unexpected payload shape."
                ) from error
            if not embeddings or len(embeddings) != len(batch):
                raise EmbeddingAPIError(
                    "Cohere embed API returned the wrong number of embeddings."
                )
            vectors.extend(embeddings)
        return vectors

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed chunks for indexing (``input_type="search_document"``)."""
        if not texts:
            return []
        return self._embed(list(texts), input_type="search_document")

    def embed_query(self, text: str) -> List[float]:
        """Embed a retrieval query (``input_type="search_query"``)."""
        return self._embed([text], input_type="search_query")[0]

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Async counterpart of :meth:`embed_documents` (uses the same endpoint)."""
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        """Async counterpart of :meth:`embed_query` (uses the same endpoint)."""
        return self.embed_query(text)


def build_embeddings() -> Any:
    """Build the process-scoped Cohere client.

    Only called on first use, so importing this module never requires
    credentials or network access. Raises immediately (rather than failing a
    user request) if ``COHERE_API_KEY`` is absent.
    """
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise EmbeddingAPIError(
            "COHERE_API_KEY must be configured to create the embedding client."
        )
    logger.info("Using Cohere embedding API (model=%s)", COHERE_EMBED_MODEL)
    return CohereEmbeddings(api_key=api_key, model=COHERE_EMBED_MODEL)


def loaded_embeddings() -> Any:
    """Return the materialized client, or ``None`` while nothing has loaded it."""
    return _EMBEDDINGS


class LazyEmbeddings(Embeddings):
    """Embeddings client that defers client construction to first use.

    Forwards to the real ``CohereEmbeddings`` instance, which is built once,
    under a lock, on the first embedding call. ``model_name`` is readable
    without constructing the client so index-provenance checks stay free.
    """

    # Read as a plain string: index provenance must not trigger a client build.
    model_name = COHERE_EMBED_MODEL

    def _resolve(self) -> Any:
        """Build the real client once, under a lock, then reuse it."""
        global _EMBEDDINGS
        if _EMBEDDINGS is not None:
            return _EMBEDDINGS
        with _EMBEDDINGS_LOCK:
            if _EMBEDDINGS is None:
                _EMBEDDINGS = build_embeddings()
        return _EMBEDDINGS

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._resolve().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._resolve().embed_query(text)

    def __getattr__(self, name: str) -> Any:
        # Only called for attributes NOT defined on this class — embed_query /
        # embed_documents / aembed_* above are already correct, so forwarding
        # here can never create infinite recursion on those. This covers
        # remaining attributes of the real client resolved on demand. Note:
        # dunder lookups bypass __getattr__, so `isinstance(proxy, Callable)`
        # and `proxy()` stay honest — this proxy is not callable, it is an
        # Embeddings object, which is exactly what FAISS validates for.
        return getattr(self._resolve(), name)

    def __repr__(self) -> str:
        state = "ready" if _EMBEDDINGS is not None else "not constructed"
        return f"<LazyEmbeddings model={COHERE_EMBED_MODEL!r} {state}>"


_SHARED_EMBEDDINGS = LazyEmbeddings()


def get_embeddings() -> LazyEmbeddings:
    """Return the process-scoped embeddings client without loading any weights."""
    return _SHARED_EMBEDDINGS