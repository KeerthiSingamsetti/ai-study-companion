"""Shared parsing helpers for evidence-backed API citations."""

from __future__ import annotations

import re


# Matches evidence markers the model may emit in realistic variants of the
# canonical [[cite:n]] form requested by the system prompt: single or double
# square/CJK brackets, optional whitespace, full-width colon, and the label
# words cite/citation/ref/source (a model that echoes the context labels
# [SOURCE:n] in its answer is still citing source n). Live capture against
# openai/gpt-oss-120b showed canonical output, but variant emission across
# many conversations would silently leak markers to the client and empty the
# Sources list, so the parser tolerates the plausible forms.
_CITATION_MARKER_PATTERN = re.compile(
    r"[\[【]{1,2}\s*(?:cite|citation|ref|source)\s*[:：]?\s*(\d+)\s*[\]】]{1,2}",
    re.IGNORECASE,
)
_GROUNDED_REFUSAL_PHRASES: tuple[str, ...] = (
    "i couldn't find enough evidence",
    "i could not find enough evidence",
    "insufficient evidence",
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
    cleaned = _CITATION_MARKER_PATTERN.sub("", response_text)
    # Collapse the double space a removed marker leaves between words, and the
    # lone space before punctuation when the marker sat directly before it
    # ("sunlight [[cite:1]]." -> "sunlight.").
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return re.sub(r" +([.,;:!?])", r"\1", cleaned).strip()
