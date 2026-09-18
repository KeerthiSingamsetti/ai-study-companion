"""Learning-loop policy: concept resolution, adaptation, growth and next steps.

State-changing helpers intentionally remain application-internal.  Only the
read-only recommendation query is suitable for a model-facing tool.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import CONCEPT_MATCH_THRESHOLD, REPEATED_MISTAKE_THRESHOLD, REPEATED_MISTAKE_WINDOW
from app.db import crud
from app.db.models import AssessmentAttempt, Concept
from app.services import calibration as calibration_service

# How many recent evidence points feed the repeated-mistake signal.
RECOMMENDATION_EVIDENCE_WINDOW = 10


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


# ---------------------------------------------------------------------------
# Growth over time
# ---------------------------------------------------------------------------

def mastery_history_by_concept(db: Session, *, user_id: str, project_id: str, limit: int = 400) -> dict[str, list[dict]]:
    """Chronological mastery evidence per concept, read from the audit event log.

    Mastery is an estimate that must evolve as new evidence arrives, so the
    ``mastery_updated`` events (not just the current score) are the source of
    truth for "how did this concept change over time".
    """
    history: dict[str, list[dict]] = {}
    events = crud.list_events_for_project(db, project_id, limit=limit)
    for event in sorted(events, key=lambda item: (item.created_at, item.id)):
        if event.event_type != "mastery_updated" or event.user_id != user_id:
            continue
        try:
            payload = json.loads(event.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        concept_id = payload.get("concept_id")
        if not concept_id:
            continue
        history.setdefault(concept_id, []).append(
            {
                "at": event.created_at.isoformat(),
                "score": payload.get("mastery_score"),
                "previous": payload.get("previous_score"),
                "evidence": payload.get("evidence_score"),
            }
        )
    return history


def summarize_concept_growth(points: Sequence[dict]) -> dict[str, Any]:
    """Turn a concept's evidence timeline into improving / stable / needs attention."""
    scores = [point.get("score") for point in points if isinstance(point.get("score"), (int, float))]
    if not scores:
        return {"classification": "stable", "delta": 0.0, "samples": 0, "previous": None, "current": None}
    current = float(scores[-1])
    previous = float(scores[-2]) if len(scores) >= 2 else float(points[-1].get("previous") or current)
    return {
        "classification": classify_growth(previous, current),
        "delta": round(current - previous, 2),
        "samples": len(scores),
        "previous": round(previous, 2),
        "current": round(current, 2),
    }


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def build_recommendations(db: Any, *, user_id: str, project_id: str) -> list[dict[str, str]]:
    """Derive next actions from persisted evidence without mutating state."""
    results: list[dict[str, str]] = []
    for concept, mastery in crud.list_mastery_for_user_and_project(db, user_id, project_id):
        attempts = (db.query(AssessmentAttempt).filter(
            AssessmentAttempt.user_id == user_id, AssessmentAttempt.project_id == project_id,
            AssessmentAttempt.concept_id == concept.id
        ).order_by(AssessmentAttempt.created_at.desc()).limit(10).all())
        scores = [attempt.overall_score for attempt in attempts]
        # Confidence calibration is a second, independent signal: a learner who
        # expects more than they produce will not study, because they believe the
        # material is already known. That outranks a low score on its own.
        calibration = calibration_service.concept_snapshot(
            concept.name,
            [
                (attempt.predicted_score, attempt.overall_score)
                for attempt in attempts
                if attempt.predicted_score is not None
            ],
        )
        if repeated_mistake_detected(scores):
            results.append({"concept": concept.name, "trigger": "repeated_mistake", "action": f"Review {concept.name} with a worked example, then retry a short assessment."})
        elif calibration["direction"] == calibration_service.DIRECTION_OVERCONFIDENT:
            results.append({
                "concept": concept.name,
                "trigger": "overconfidence",
                "action": (
                    f"You predicted {calibration['mean_predicted']:.0f}/100 on {concept.name} but averaged "
                    f"{calibration['mean_actual']:.0f}/100. Prove it closed-book — no notes, then one short assessment."
                ),
            })
        elif mastery.mastery_score < 60:
            results.append({"concept": concept.name, "trigger": "low_mastery", "action": f"Review {concept.name} and complete targeted practice."})
        elif len(scores) >= 2 and classify_growth(scores[1], scores[0]) == "improving":
            results.append({"concept": concept.name, "trigger": "improving", "action": f"Continue practising {concept.name} with an application question."})
    return results[:3]


def refresh_recommendations(db: Session, *, user_id: str, project_id: str) -> list[Any]:
    """Materialise derived recommendations so they persist across sessions.

    Each recommendation is stored once per (project, concept, trigger, text)
    combination; re-running after new evidence refreshes the guidance instead
    of duplicating it.
    """
    derived = build_recommendations(db, user_id=user_id, project_id=project_id)
    active = crud.list_active_recommendations_for_project(db, user_id, project_id)
    by_concept = {row.concept_id: row for row in active}

    concepts = {concept.id: concept for concept in crud.list_concepts_for_project(db, project_id)}
    concept_by_name = {concept.name: concept for concept in concepts.values()}
    created = 0

    for item in derived:
        concept = concept_by_name.get(item["concept"])
        concept_id = concept.id if concept is not None else None
        if concept_id and concept_id in by_concept:
            existing = by_concept[concept_id]
            if existing.recommendation == item["action"] and existing.trigger == item["trigger"]:
                continue
            existing.is_dismissed = True
            db.commit()
        digest = hashlib.sha1(f"{project_id}:{item['trigger']}:{item['concept']}:{item['action']}".encode()).hexdigest()[:12]
        event_key = f"recommendation:{digest}"
        if crud.event_exists(db, event_key):
            continue
        crud.create_recommendation(
            db,
            user_id=user_id,
            project_id=project_id,
            concept_id=concept_id,
            trigger=item["trigger"],
            recommendation=item["action"],
        )
        crud.log_event(
            db,
            event_key=event_key,
            user_id=user_id,
            project_id=project_id,
            event_type="recommendations_generated",
            payload_json=json.dumps({"concept": item["concept"], "trigger": item["trigger"]}),
        )
        created += 1

    return crud.list_active_recommendations_for_project(db, user_id, project_id)
