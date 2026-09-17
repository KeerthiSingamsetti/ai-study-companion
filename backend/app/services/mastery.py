"""Deterministic concept-mastery updates for the learning loop."""

from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import MASTERY_INITIAL_SCORE, MASTERY_LAMBDA
from app.db import crud
from app.db.models import ConceptMastery


def calculate_ema_mastery(previous_score: float, evidence_score: float) -> float:
    """Return ``λ * previous + (1 - λ) * evidence`` on the 0--100 scale.

    ``λ=0.85`` deliberately makes a single answer informative without letting
    it erase the learner's accumulated history.
    """
    if not 0.0 <= evidence_score <= 100.0:
        raise ValueError("evidence_score must be between 0 and 100.")
    if not 0.0 <= previous_score <= 100.0:
        raise ValueError("previous_score must be between 0 and 100.")
    return round(MASTERY_LAMBDA * previous_score + (1.0 - MASTERY_LAMBDA) * evidence_score, 2)


def update_concept_mastery(
    db: Session,
    *,
    user_id: str,
    project_id: str,
    concept_id: str,
    evidence_score: float,
    event_key: str | None = None,
) -> ConceptMastery:
    """Apply one assessment evidence point and create an idempotent audit event."""
    concept = next(
        (item for item in crud.list_concepts_for_project(db, project_id) if item.id == concept_id),
        None,
    )
    if concept is None:
        raise ValueError("Concept does not belong to this project.")

    resolved_event_key = event_key or f"mastery:{user_id}:{concept_id}:{uuid4()}"
    # An already accepted event must never apply EMA evidence a second time.
    if crud.event_exists(db, resolved_event_key):
        existing_mastery = crud.get_concept_mastery(db, user_id, concept_id)
        if existing_mastery is None:
            raise RuntimeError("Mastery event exists without a mastery record.")
        return existing_mastery

    existing = crud.get_concept_mastery(db, user_id, concept_id)
    previous = existing.mastery_score if existing is not None else MASTERY_INITIAL_SCORE
    updated = calculate_ema_mastery(previous, evidence_score)
    mastery = crud.upsert_concept_mastery(
        db, user_id=user_id, concept_id=concept_id, mastery_score=updated
    )
    crud.log_event(
        db,
        event_key=resolved_event_key,
        user_id=user_id,
        project_id=project_id,
        event_type="mastery_updated",
        payload_json=json.dumps({
            "concept_id": concept_id,
            "previous_score": previous,
            "evidence_score": evidence_score,
            "mastery_score": updated,
        }),
    )
    return mastery
