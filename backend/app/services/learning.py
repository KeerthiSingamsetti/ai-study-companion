"""Learning-loop policy: concept resolution, adaptation, growth and next steps.

State-changing helpers intentionally remain application-internal.  Only the
read-only recommendation query is suitable for a model-facing tool.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import CONCEPT_MATCH_THRESHOLD, REPEATED_MISTAKE_THRESHOLD, REPEATED_MISTAKE_WINDOW
from app.db import crud
from app.db.models import Concept


def normalize_concept_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", name.lower())).strip()


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right)) / (math.sqrt(sum(a*a for a in left)) * math.sqrt(sum(b*b for b in right)) + 1e-12)


def resolve_concept(db: Session, *, project_id: str, name: str, embeddings: Any) -> Concept:
    """Resolve exact normalized name, then NIM embedding similarity >= 0.88."""
    normalized = normalize_concept_name(name)
    if not normalized:
        raise ValueError("Concept name cannot be empty.")
    exact = crud.get_concept_by_normalized_name(db, project_id, normalized)
    if exact is not None:
        return exact
    concepts = crud.list_concepts_for_project(db, project_id)
    if concepts:
        vectors = embeddings.embed_documents([concept.name for concept in concepts])
        query = embeddings.embed_query(name)
        best, score = max(((concept, _cosine(query, vector)) for concept, vector in zip(concepts, vectors)), key=lambda pair: pair[1])
        if score >= CONCEPT_MATCH_THRESHOLD:
            return best
    return crud.create_concept(db, concept_id=str(uuid4()), project_id=project_id, name=name.strip(), name_normalized=normalized)


def classify_growth(previous_score: float, current_score: float) -> str:
    """Classify meaningful movement without overstating small EMA changes."""
    delta = current_score - previous_score
    if delta >= 3:
        return "improving"
    if delta <= -3 or current_score < 60:
        return "needs_attention"
    return "stable"


def choose_adaptive_concept(mastery_rows: Sequence[tuple[Concept, Any]], recent_mistake_counts: dict[str, int]) -> tuple[Concept, str]:
    """Select by mastery and repeated mistakes, rather than one-answer difficulty flips."""
    if not mastery_rows:
        raise ValueError("No concepts have mastery evidence yet.")
    concept, mastery = max(
        mastery_rows,
        key=lambda row: (100 - row[1].mastery_score) + 12 * recent_mistake_counts.get(row[0].id, 0),
    )
    score = mastery.mastery_score
    difficulty = "easy" if score < 45 else "medium" if score < 75 else "hard"
    return concept, difficulty


def repeated_mistake_detected(recent_evidence_scores: Sequence[float]) -> bool:
    """Flag three low-scoring attempts in the latest ten evidence points."""
    return sum(score < 60 for score in recent_evidence_scores[:REPEATED_MISTAKE_WINDOW]) >= REPEATED_MISTAKE_THRESHOLD
