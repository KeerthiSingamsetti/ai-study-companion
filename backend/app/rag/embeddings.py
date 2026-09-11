"""Shared NVIDIA embedding provider for StudyMate RAG operations."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

_BACKEND_DIR = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_embeddings() -> NVIDIAEmbeddings:
    """Return the process-scoped embeddings client used for indexing and retrieval.

    This preserves the Module 2 NVIDIA configuration and ensures an embeddings
    client is constructed only once per process.
    """
    load_dotenv(_BACKEND_DIR / ".env", override=False)
    return NVIDIAEmbeddings(
        model="nvidia/nv-embedqa-e5-v5",
        api_key=os.getenv("NVIDIA_API_KEY"),
        truncate="END",
    )
