"""Process/container memory introspection.

Deliberately dependency-free and import-light: this module is imported at the
very top of ``app.main`` — before numpy/faiss/langchain — so it can influence
which features are enabled, and by ``app.services.ingestion_worker`` so long
ingestions can stop before the platform OOM-kills the container.

Why this exists: a compact deployment (Render free tier = 512MB) does not have
room for the whole stack at full tilt. Being OOM-killed is the worst possible
failure mode — the service returns 502 for every user, the process dies
mid-ingestion, and nothing tells the user what happened. Detecting the limit
and *aborting the work cleanly* turns that into an ordinary, retryable job
failure with an actionable message.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# cgroup v2 and v1 memory limit files (Render, Fly, Docker, Kubernetes).
_CGROUP_V2_LIMIT = Path("/sys/fs/cgroup/memory.max")
_CGROUP_V1_LIMIT = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
# Kernels report "unlimited" as a sentinel near 2**63; anything this large is
# not a real constraint.
_UNLIMITED_THRESHOLD_MB = 1_000_000.0

# Leave this much room for the interpreter, the web layer, and request churn.
# Below it, ingestion is refused rather than attempted.
INGESTION_MIN_HEADROOM_MB = 150.0
# During embedding, abort if the resident set climbs past this fraction of the
# container limit — the FAISS build and response handling still need room.
INGESTION_ABORT_FRACTION = 0.85
# Reranking loads a local torch cross-encoder (~1.5GB resident). Instances
# smaller than this cannot run it without being OOM-killed.
RERANKING_MIN_LIMIT_MB = 2048.0


class MemoryBudgetError(RuntimeError):
    """Raised when an operation cannot complete inside this container's memory."""


def _read_limit_mb(path: Path) -> Optional[float]:
    """Parse one cgroup limit file, returning MB or None when unusable."""
    try:
        raw = path.read_text(encoding="ascii").strip()
    except OSError:
        return None
    if not raw or raw == "max":
        return None  # v2's explicit "unlimited" marker
    try:
        limit_mb = int(raw) / 1024 / 1024
    except ValueError:
        return None
    if limit_mb <= 0 or limit_mb >= _UNLIMITED_THRESHOLD_MB:
        return None
    return limit_mb


def memory_limit_mb() -> Optional[float]:
    """Container memory limit in MB, or None when it cannot be determined.

    ``MEMORY_LIMIT_MB`` overrides detection (used by tests and by operators on
    platforms that expose the limit some other way). A None result means
    "unknown", and callers must treat unknown as no constraint rather than as
    zero headroom.
    """
    override = os.getenv("MEMORY_LIMIT_MB")
    if override:
        try:
            parsed = float(override)
            return parsed if parsed > 0 else None
        except ValueError:
            logger.warning("Ignoring invalid MEMORY_LIMIT_MB=%r", override)
    for path in (_CGROUP_V2_LIMIT, _CGROUP_V1_LIMIT):
        limit = _read_limit_mb(path)
        if limit is not None:
            return limit
    return None


def process_rss_mb() -> Optional[float]:
    """Best-effort resident memory of this process in MB, or None if unknown."""
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as handle:
            pages = int(handle.read().split()[1])
        return round(pages * (os.sysconf("SC_PAGE_SIZE") / 1024 / 1024), 1)
    except (OSError, ValueError, AttributeError, IndexError):
        return None


def memory_headroom_mb() -> Optional[float]:
    """MB available before hitting the container limit, or None if unknown."""
    limit = memory_limit_mb()
    rss = process_rss_mb()
    if limit is None or rss is None:
        return None
    return round(limit - rss, 1)


def describe_memory() -> str:
    """One-line human summary for startup logs and the health endpoint."""
    limit = memory_limit_mb()
    rss = process_rss_mb()
    limit_text = f"{limit:.0f} MB" if limit is not None else "undetected"
    rss_text = f"{rss:.1f} MB" if rss is not None else "unknown"
    headroom = memory_headroom_mb()
    headroom_text = f", headroom {headroom:.0f} MB" if headroom is not None else ""
    return f"limit {limit_text}, RSS {rss_text}{headroom_text}"


def has_room_for_ingestion() -> bool:
    """Whether there is enough headroom to start parsing/embedding a PDF.

    Unknown limits always pass: refusing work on an undetectable platform
    would be worse than the out-of-memory risk it guards against.
    """
    headroom = memory_headroom_mb()
    if headroom is None:
        return True
    return headroom >= INGESTION_MIN_HEADROOM_MB


def exceeds_abort_threshold() -> bool:
    """Whether the process has grown too close to the container limit.

    Checked between embedding batches, which is where this stack's memory
    actually climbs (vectors, FAISS build, batch payloads).
    """
    limit = memory_limit_mb()
    rss = process_rss_mb()
    if limit is None or rss is None:
        return False
    return rss >= limit * INGESTION_ABORT_FRACTION


def memory_budget_message() -> str:
    """Actionable, user-facing explanation of a memory refusal."""
    limit = memory_limit_mb()
    rss = process_rss_mb()
    limit_text = f"{limit:.0f} MB" if limit is not None else "unknown"
    rss_text = f"{rss:.0f} MB" if rss is not None else "unknown"
    return (
        f"This server ran out of memory while processing the PDF "
        f"(instance limit {limit_text}, in use {rss_text}). "
        "Try a smaller PDF, or upgrade the instance to one with more memory."
    )


def reranking_is_feasible() -> bool:
    """Whether this instance has room for the local torch cross-encoder."""
    limit = memory_limit_mb()
    if limit is None:
        return True  # unknown platform: leave the operator's choice alone
    return limit >= RERANKING_MIN_LIMIT_MB
