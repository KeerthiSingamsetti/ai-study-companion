"""Shared parsing helpers for evidence-backed API citations."""

from __future__ import annotations

import re


_CITATION_MARKER_PATTERN = re.compile(r"\[\[cite:(\d+)\]\]", re.IGNORECASE)
_GROUNDED_REFUSAL_PHRASES: tuple[str, ...] = (
    "i couldn't find information about",
    "the provided context does not contain enough information",
    "no relevant uploaded-document context was found",
    "no uploaded documents are available",
    "i could not find information about",
    "the context does not contain",
    "not found in the uploaded",
    "not available in the uploaded",
)


def is_grounded_refusal(response_text: str) -> bool:
    """Return whether an answer explicitly says the retrieved context was insufficient."""
    lowered = response_text.lower()
    return any(phrase in lowered for phrase in _GROUNDED_REFUSAL_PHRASES)


def extract_citation_ids(response_text: str) -> list[int]:
    """Return unique, in-order source IDs explicitly selected by the model."""
    selected_ids: list[int] = []
    seen: set[int] = set()
    for match in _CITATION_MARKER_PATTERN.finditer(response_text):
        citation_id = int(match.group(1))
        if citation_id not in seen:
            seen.add(citation_id)
            selected_ids.append(citation_id)
    return selected_ids


def strip_citation_markers(response_text: str) -> str:
    """Remove internal evidence markers before returning an answer to an API client."""
    return _CITATION_MARKER_PATTERN.sub("", response_text).replace("  ", " ").strip()
