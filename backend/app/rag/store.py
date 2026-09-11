"""
FAISS vector store persistence layer for StudyMate RAG pipeline.

Handles building, saving, loading, and deleting vector indexes on disk.
This module isolates all disk I/O for vector stores.

Also persists the raw chunk list (chunks.pkl) alongside the FAISS index,
since hybrid search (BM25 + dense) needs the original chunk text in memory
to reconstruct a BM25Retriever - FAISS itself only stores vectors.

Note: This module assumes single-writer access per save_path. Concurrent
rebuild or deletion of an index while a query is in flight against the
same path is not currently guarded against.
"""
import os
import pickle
import shutil
import logging
import hashlib
import json
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from app.rag.exceptions import VectorStoreLoadError

logger = logging.getLogger(__name__)

CHUNKS_FILENAME = "chunks.pkl"
INDEX_METADATA_FILENAME = "index_metadata.json"
INDEX_METADATA_SCHEMA_VERSION = 1
_INDEX_CACHE: dict[tuple[str, str, str], FAISS] = {}
_INDEX_CACHE_LOCK = threading.Lock()


def embedding_identifier(embeddings: Any) -> str:
    """Return a stable, human-readable identifier for an embeddings instance."""
    for attribute in ("model_name", "model", "model_id"):
        value = getattr(embeddings, attribute, None)
        if isinstance(value, str) and value:
            return value
    return f"{type(embeddings).__module__}.{type(embeddings).__qualname__}"


def load_index_metadata(save_path: str) -> Optional[dict[str, Any]]:
    """Load optional index provenance metadata, or None for legacy indexes."""
    metadata_path = Path(save_path) / INDEX_METADATA_FILENAME
    if not metadata_path.exists():
        return None
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VectorStoreLoadError(
            f"Index metadata is unreadable at {metadata_path}: {error}", save_path
        ) from error
    if not isinstance(payload, dict):
        raise VectorStoreLoadError(
            f"Index metadata is invalid at {metadata_path}", save_path
        )
    return payload


def index_fingerprint(save_path: str) -> str:
    """Return a cache-safe identity that changes when an index is rebuilt."""
    metadata = load_index_metadata(save_path)
    index_directory = Path(save_path)
    parts = [str(metadata.get("index_id", "legacy")) if metadata else "legacy"]
    # Include every persisted artifact so cache entries cannot survive a
    # partial rebuild, corruption, or manual index replacement.
    for filename in ("index.faiss", "index.pkl", CHUNKS_FILENAME, INDEX_METADATA_FILENAME):
        path = index_directory / filename
        try:
            stat = path.stat()
            parts.append(f"{filename}:{stat.st_size}:{stat.st_mtime_ns}")
        except OSError:
            parts.append(f"{filename}:missing")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clear_index_cache(save_path: Optional[str] = None) -> None:
    """Evict one index, or all indexes, from the in-process FAISS cache."""
    with _INDEX_CACHE_LOCK:
        if save_path is None:
            _INDEX_CACHE.clear()
            return
        resolved = str(Path(save_path).resolve())
        for key in list(_INDEX_CACHE):
            if key[0] == resolved:
                _INDEX_CACHE.pop(key, None)


def _write_index_metadata(save_path: str, payload: Mapping[str, Any]) -> None:
    metadata_path = Path(save_path) / INDEX_METADATA_FILENAME
    temporary_path = metadata_path.with_suffix(".tmp")
    try:
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary_path.replace(metadata_path)
    except OSError as error:
        raise VectorStoreLoadError(
            f"Failed to persist index metadata at {metadata_path}: {error}", save_path
        ) from error


def build_and_save_index(
    chunks: List[Document],
    embeddings,
    save_path: str,
    *,
    index_metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    """
    Builds a FAISS index from document chunks and saves it to a local directory.
    Also pickles the chunk list alongside it, so hybrid search can later
    reconstruct a BM25Retriever without needing the original PDF again.

    WARNING: The `embeddings` parameter must be an instantiated embeddings
    model. Callers should instantiate the model ONCE at startup and pass
    it in to avoid expensive per-call reloads.

    Args:
        chunks: List of LangChain Document objects to index.
        embeddings: The embedding model instance to generate vectors.
        save_path: Directory path where the index files will be saved.
        index_metadata: Optional provenance such as chunk size or corpus ID.
            The storage layer always adds embedding identity, dimension, a
            rebuild ID, and corpus summary fields.

    Raises:
        ValueError: If chunks list is empty.
    """
    if not chunks:
        raise ValueError("Cannot build a FAISS index from an empty chunk list.")

    clear_index_cache(save_path)
    # FAISS.save_local() automatically creates the directory if it doesn't exist
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(save_path)

    chunks_path = os.path.join(save_path, CHUNKS_FILENAME)
    with open(chunks_path, "wb") as f:
        pickle.dump(chunks, f)

    sources = sorted({str(chunk.metadata.get("source", "Unknown")) for chunk in chunks})
    pages = [chunk.metadata.get("page") for chunk in chunks]
    metadata = dict(index_metadata or {})
    metadata.update({
        "schema_version": INDEX_METADATA_SCHEMA_VERSION,
        "index_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "embedding_identifier": embedding_identifier(embeddings),
        "embedding_dimension": int(vectorstore.index.d),
        "chunk_count": len(chunks),
        "source_count": len(sources),
        "sources": sources,
        "page_count": len({page for page in pages if page is not None}),
    })
    _write_index_metadata(save_path, metadata)
    clear_index_cache(save_path)

    logger.info(
        f"Successfully saved FAISS index and {len(chunks)} chunk(s) to {save_path}."
    )


def load_index(
    save_path: str,
    embeddings,
    *,
    validate_embedding: bool = True,
) -> Optional[FAISS]:
    """
    Loads a FAISS index from a local directory.

    Args:
        save_path: Directory path containing index.faiss and index.pkl.
        embeddings: The embedding model instance to generate vectors. MUST
                    be the same model (and dimensionality) used when the
                    index was built - switching embedding models requires
                    rebuilding the index from scratch.

    Returns:
        The FAISS vectorstore instance, or None if the directory doesn't exist.

    Raises:
        VectorStoreLoadError: If the directory exists but the files inside
                              are corrupted, unreadable, or dimension-mismatched
                              against the given embeddings model.
    """
    if not os.path.exists(save_path):
        return None

    try:
        metadata = load_index_metadata(save_path)
        if validate_embedding and metadata:
            stored_identifier = metadata.get("embedding_identifier")
            requested_identifier = embedding_identifier(embeddings)
            if stored_identifier and stored_identifier != requested_identifier:
                raise VectorStoreLoadError(
                    "Index embeddings do not match the requested embeddings "
                    f"({stored_identifier!r} != {requested_identifier!r}). "
                    "Rebuild the index before retrieving.",
                    save_path,
                )
        cache_key = (
            str(Path(save_path).resolve()),
            embedding_identifier(embeddings),
            index_fingerprint(save_path),
        )
        with _INDEX_CACHE_LOCK:
            cached = _INDEX_CACHE.get(cache_key)
        if cached is not None:
            return cached
        # allow_dangerous_deserialization=True is required by recent LangChain
        # versions because FAISS unpickles metadata. This is safe here because
        # we only load local files we generated ourselves, not user uploads.
        loaded = FAISS.load_local(
            save_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        with _INDEX_CACHE_LOCK:
            # Remove stale incarnations of this path before saving the new one.
            resolved = cache_key[0]
            for key in list(_INDEX_CACHE):
                if key[0] == resolved and key != cache_key:
                    _INDEX_CACHE.pop(key, None)
            _INDEX_CACHE[cache_key] = loaded
        return loaded
    except VectorStoreLoadError:
        raise
    except Exception as e:
        raise VectorStoreLoadError(
            f"Failed to load FAISS index from {save_path}. It may be corrupted, "
            f"missing index files, or built with a different embeddings model "
            f"(dimension mismatch). Details: {str(e)}",
            save_path=save_path,
        ) from e


def load_chunks(save_path: str) -> Optional[List[Document]]:
    """
    Loads the pickled chunk list saved alongside a FAISS index. Required
    for hybrid search (BM25Retriever needs raw chunk text, not just vectors).

    Args:
        save_path: Directory path containing chunks.pkl.

    Returns:
        The list of Document chunks, or None if chunks.pkl doesn't exist
        (e.g. an index built before hybrid search was added).

    Raises:
        VectorStoreLoadError: If chunks.pkl exists but is corrupted/unreadable.
    """
    chunks_path = os.path.join(save_path, CHUNKS_FILENAME)
    if not os.path.exists(chunks_path):
        return None

    try:
        with open(chunks_path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        raise VectorStoreLoadError(
            f"Failed to load chunks.pkl from {save_path}. It may be corrupted. "
            f"Details: {str(e)}",
            save_path=save_path,
        ) from e


def load_ordered_chunks(save_path: str) -> Optional[List[Document]]:
    """
    Loads all pickled Document chunks for a document index in original document order.

    Ensures chunks are sorted deterministically by chunk_index (or page index).

    Args:
        save_path: Directory path containing chunks.pkl.

    Returns:
        The list of Document chunks sorted by original position, or None if missing.
    """
    chunks = load_chunks(save_path)
    if chunks is None:
        return None

    return sorted(
        chunks,
        key=lambda chunk: (
            chunk.metadata.get("chunk_index", 0),
            chunk.metadata.get("page", 0),
        ),
    )


def delete_index(save_path: str) -> bool:
    """
    Safely deletes a FAISS index directory tree (including chunks.pkl).

    Args:
        save_path: Directory path of the index to delete.

    Returns:
        True if a directory was deleted, False if the directory didn't exist (no-op).
    """
    if not os.path.exists(save_path):
        return False

    clear_index_cache(save_path)
    shutil.rmtree(save_path, ignore_errors=True)
    return True
