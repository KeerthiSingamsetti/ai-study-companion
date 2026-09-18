"""Confidence calibration: does a learner know what they don't know?

The PRD asks the system to "identify weaknesses" and recommend what to do next,
but every signal it describes measures *produced* knowledge — what a learner can
answer when asked. Self-assessment is a second, independent signal, and the gap
between the two is the most actionable thing in a learning product: a learner
who rates themselves certain and scores 46% is not going to study, because they
believe they already know it. Recognising material is not the same as being able
to produce it, and only a prediction-versus-result comparison exposes the gap.

Design decisions, deliberately mirroring the mastery maths:

* **Deterministic.** Bias is arithmetic over stored evidence. The LLM grades the
  answer; it never judges the learner's self-awareness — that would be both
  unauditable and easy to flatter.
* **One tap, not a questionnaire.** A 5-point confidence scale is mapped to a
  0-100 prediction so it is directly comparable with the graded score.
* **Evidence accumulates.** A single overconfident answer means little; a
  repeated bias on the same concept is a study-plan-level insight.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.config import (
    CALIBRATION_MIN_SAMPLES,
    CALIBRATION_OVERCONFIDENT_GAP,
    CALIBRATION_UNDERCONFIDENT_GAP,
)
from app.db.models import AssessmentAttempt, Concept

# Ordered self-report scale. Sparse on purpose: a learner can pick confidently
# between five options in under a second, which is what keeps the ritual cheap.
CONFIDENCE_SCALE: tuple[tuple[int, float, str], ...] = (
    (1, 20.0, "Guess"),
    (2, 40.0, "Not sure"),
    (3, 60.0, "Fairly sure"),
    (4, 80.0, "Confident"),
    (5, 100.0, "Certain"),
)

DIRECTION_OVERCONFIDENT = "overconfident"
DIRECTION_UNDERCONFIDENT = "underconfident"
DIRECTION_CALIBRATED = "well_calibrated"
DIRECTION_INSUFFICIENT = "insufficient_evidence"


def predicted_from_confidence(level: int) -> float | None:
    """Map a 1-5 self-report onto a 0-100 prediction, or None if unrecognised."""
    for value, score, _ in CONFIDENCE_SCALE:
        if int(level) == value:
            return score
    return None


def confidence_label(level: int) -> str:
    """Human label for one step of the self-report scale."""
    for value, _, label in CONFIDENCE_SCALE:
        if int(level) == value:
            return label
    return "Unknown"


def _direction(bias: float, samples: int) -> str:
    if samples < CALIBRATION_MIN_SAMPLES:
        return DIRECTION_INSUFFICIENT
    if bias >= CALIBRATION_OVERCONFIDENT_GAP:
        return DIRECTION_OVERCONFIDENT
    if bias <= CALIBRATION_UNDERCONFIDENT_GAP:
        return DIRECTION_UNDERCONFIDENT
    return DIRECTION_CALIBRATED


def summarize(pairs: Sequence[tuple[float, float]]) -> dict[str, Any]:
    """Summarise (predicted, actual) pairs into bias and calibration error.

    ``bias`` is signed: positive means the learner expected more than they
    produced. ``mean_absolute_error`` is the size of the miss regardless of
    direction, i.e. how well the learner's self-model tracks reality.
    """
    usable = [(float(p), float(a)) for p, a in pairs if p is not None and a is not None]
    if not usable:
        return {
            "samples": 0,
            "mean_predicted": None,
            "mean_actual": None,
            "bias": None,
            "mean_absolute_error": None,
            "direction": DIRECTION_INSUFFICIENT,
        }
    count = len(usable)
    mean_predicted = sum(p for p, _ in usable) / count
    mean_actual = sum(a for _, a in usable) / count
    bias = mean_predicted - mean_actual
    error = sum(abs(p - a) for p, a in usable) / count
    return {
        "samples": count,
        "mean_predicted": round(mean_predicted, 1),
        "mean_actual": round(mean_actual, 1),
        "bias": round(bias, 1),
        "mean_absolute_error": round(error, 1),
        "direction": _direction(bias, count),
    }


def insight(concept: str, summary: dict[str, Any]) -> str:
    """One actionable sentence explaining what the numbers mean."""
    direction = summary.get("direction")
    predicted = summary.get("mean_predicted")
    actual = summary.get("mean_actual")
    error = summary.get("mean_absolute_error")

    if direction == DIRECTION_INSUFFICIENT or predicted is None:
        return f"Predict your score before grading a few more answers on {concept} to build a calibration signal."
    if direction == DIRECTION_OVERCONFIDENT:
        return (
            f"You rated yourself {predicted:.0f}/100 on {concept} but scored {actual:.0f}/100 — "
            f"{summary['bias']:.0f} points of confidence you cannot yet produce. "
            "Rehearse it closed-book and re-test: recognising the material is not the same as retrieving it."
        )
    if direction == DIRECTION_UNDERCONFIDENT:
        return (
            f"You rated yourself {predicted:.0f}/100 on {concept} and scored {actual:.0f}/100 — "
            "you know more than you credited yourself for. Attempt a harder question on it."
        )
    return (
        f"Your self-assessment on {concept} tracks your results to within {error:.0f} points "
        f"({predicted:.0f}/100 predicted vs {actual:.0f}/100 scored). "
        "Your own estimate is currently a trustworthy signal."
    )


def headline(report: dict[str, Any]) -> str:
    """Project-level sentence for the calibration panel."""
    if report["samples"] == 0:
        return (
            "No calibration evidence yet. Rate your confidence before submitting an answer "
            "and the system can tell you where your self-assessment drifts."
        )
    worst = next(
        (row for row in report["concepts"] if row["direction"] == DIRECTION_OVERCONFIDENT),
        None,
    )
    if worst is not None:
        return (
            f"Across {report['samples']} rated answer{'' if report['samples'] == 1 else 's'} you expect "
            f"{report['bias']:.0f} points more than you produce, most of it on {worst['concept']}. "
            "That gap is why material can feel familiar and still fail in an exam — practise retrieval, not review."
        )
    best = next(
        (row for row in report["concepts"] if row["direction"] == DIRECTION_UNDERCONFIDENT),
        None,
    )
    if best is not None:
        return (
            f"You consistently under-rate yourself (by {abs(report['bias']):.0f} points on average), "
            f"most on {best['concept']}. Your knowledge is ahead of your confidence — attempt harder questions."
        )
    return (
        f"Your predictions track your graded results to within {report['mean_absolute_error']:.0f} points. "
        "You have an accurate picture of what you know, which makes your own next-step choices reliable."
    )


def concept_rows(db: Session, *, user_id: str, project_id: str) -> list[dict[str, Any]]:
    """Per-concept calibration, strongest bias first, from persisted evidence."""
    attempts = (
        db.query(AssessmentAttempt, Concept.name)
        .outerjoin(Concept, Concept.id == AssessmentAttempt.concept_id)
        .filter(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.project_id == project_id,
            AssessmentAttempt.predicted_score.isnot(None),
        )
        .order_by(AssessmentAttempt.created_at.asc())
        .all()
    )
    grouped: dict[str, list[tuple[float, float]]] = {}
    names: dict[str, str] = {}
    for attempt, name in attempts:
        key = attempt.concept_id or "unassigned"
        names.setdefault(key, name or "Unassigned concept")
        grouped.setdefault(key, []).append((attempt.predicted_score, attempt.overall_score))

    rows = []
    for concept_id, pairs in grouped.items():
        summary = summarize(pairs)
        rows.append({"concept_id": concept_id, "concept": names[concept_id], **summary, "insight": insight(names[concept_id], summary)})
    return sorted(rows, key=lambda row: abs(row["bias"] or 0), reverse=True)


def report(db: Session, *, user_id: str, project_id: str) -> dict[str, Any]:
    """Full calibration view for one Project: overall plus per-concept detail."""
    rows = concept_rows(db, user_id=user_id, project_id=project_id)
    pairs = [
        (attempt.predicted_score, attempt.overall_score)
        for attempt in db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.project_id == project_id,
            AssessmentAttempt.predicted_score.isnot(None),
        )
        .all()
    ]
    summary = summarize(pairs)
    payload = {"project_id": project_id, **summary, "concepts": rows}
    payload["overconfidence_gap"] = summary["bias"] if summary["direction"] == DIRECTION_OVERCONFIDENT else None
    payload["headline"] = headline(payload)
    return payload


def concept_snapshot(
    concept: str,
    pairs: Sequence[tuple[float, float]],
) -> dict[str, Any]:
    """Calibration for the concept just answered, to show right after grading."""
    summary = summarize(pairs)
    return {"concept": concept, **summary, "insight": insight(concept, summary)}
