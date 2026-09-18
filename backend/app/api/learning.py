"""Authenticated learning-loop API: evidence in, mastery/growth/next steps out.

This router closes the loop the PRD describes. Two kinds of evidence feed the
same concept-mastery estimate:

* **Adaptive quiz** — multiple-choice results arrive through ``/learning/quiz-result``.
* **Open-ended assessment** — explanation-style answers are generated, graded and
  persisted through ``/learning/assessment/*``.

Both paths resolve the concept, apply the deterministic recency-weighted EMA
(:mod:`app.services.mastery`), write an idempotent audit event, and refresh the
persisted recommendations, so Project Analytics and the Home dashboard always
read real, evolving evidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_embeddings, get_llm
from app.config import REPEATED_MISTAKE_WINDOW
from app.db import crud
from app.db.models import AssessmentAttempt, Document, User
from app.db.session import get_db
from app.rag.exceptions import DocumentNotIndexedError
from app.rag.retriever import retrieve
from app.schemas.learning import (
    AssessmentGenerateRequest,
    AssessmentGenerateResponse,
    AssessmentGradeRequest,
    AssessmentGradeResponse,
    AssessmentHistoryItem,
    AssessmentQuestion,
    AssessmentSummaryResponse,
    ConceptGrowth,
    MasterySnapshot,
    QuizResultRequest,
    QuizResultResponse,
)
from app.services.grading import GradingError, grade_open_ended_answer
from app.services.learning import (
    choose_adaptive_concept,
    mastery_history_by_concept,
    refresh_recommendations,
    resolve_concept,
    summarize_concept_growth,
)
from app.services.mastery import update_concept_mastery
from app.tools.memory_tool import record_studied_topic, record_weak_topic
from app.tools.assessment_tool import (
    RUBRIC,
    AssessmentGenerationError,
    format_context,
    generate_open_ended_questions,
)

router = APIRouter(prefix="/learning", tags=["learning"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _owned_project(db: Session, project_id: str, user: User) -> Any:
    project = crud.get_thread(db, project_id, user_id=user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _project_document(db: Session, project_id: str, document_id: str | None) -> Document | None:
    """Resolve an explicit document, else the project's first uploaded material."""
    if document_id:
        document = crud.get_document(db, document_id)
        if document is None or document.thread_id != project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found in this project.")
        return document
    documents = crud.list_documents_for_thread(db, project_id)
    return documents[0] if documents else None


def _retrieve_evidence(document: Document | None, query: str, embeddings: Any, k: int = 8) -> tuple[str, str | None]:
    """Return (context, citation_hint) for a grounded assessment operation."""
    if document is None:
        return "", None
    try:
        chunks = retrieve(
            query,
            document.vectorstore_path,
            embeddings,
            use_hybrid_search=True,
            use_reranking=True,
            k=max(10, k * 2),
            rerank_top_k=k,
        )
    except DocumentNotIndexedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This material is still being processed and cannot be assessed yet.",
        ) from error
    if not chunks:
        return "", None
    top = chunks[0]
    page = (top.page + 1) if top.page is not None else None
    hint = f"{document.filename}, page {page}" if page else document.filename
    return format_context(chunks), hint


def _snapshot(db: Session, *, user_id: str, project_id: str, concept_id: str, concept_name: str) -> MasterySnapshot:
    record = crud.get_concept_mastery(db, user_id, concept_id)
    history = mastery_history_by_concept(db, user_id=user_id, project_id=project_id).get(concept_id, [])
    return MasterySnapshot(
        concept=concept_name,
        concept_id=concept_id,
        score=round(record.mastery_score, 2) if record else 0.0,
        attempts=record.attempt_count if record else 0,
        growth=summarize_concept_growth(history),
    )


def _average_assessment_score(db: Session, user_id: str, project_id: str) -> float | None:
    rows = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.user_id == user_id, AssessmentAttempt.project_id == project_id)
        .all()
    )
    if not rows:
        return None
    return round(sum(row.overall_score for row in rows) / len(rows), 2)


# ---------------------------------------------------------------------------
# Adaptive selection
# ---------------------------------------------------------------------------

@router.get("/quiz/next")
def next_adaptive_quiz_target(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Decide what this learner should be quizzed on next, and at what difficulty.

    Selection is a policy decision, not a reaction to the previous answer:
    :func:`choose_adaptive_concept` scores every concept by ``(100 - mastery)``
    plus a penalty for repeated recent mistakes, and the difficulty is derived
    from that same mastery estimate. A wrong answer therefore never directly
    forces an "easy" question — sustained low evidence does.
    """
    project = _owned_project(db, project_id, current_user)
    mastery_rows = crud.list_mastery_for_user_and_project(db, current_user.id, project.id)
    if not mastery_rows:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No concepts have mastery evidence yet. Pick a topic for this first quiz — "
                "after that, selection adapts to your results."
            ),
        )

    history = mastery_history_by_concept(db, user_id=current_user.id, project_id=project.id)
    mistake_counts: dict[str, int] = {}
    for concept, _record in mastery_rows:
        recent = history.get(concept.id, [])[-REPEATED_MISTAKE_WINDOW:]
        mistake_counts[concept.id] = sum(
            1
            for point in recent
            if isinstance(point.get("evidence"), (int, float)) and point["evidence"] < 60
        )

    try:
        concept, difficulty = choose_adaptive_concept(mastery_rows, mistake_counts)
    except ValueError as error:  # pragma: no cover - guarded by the check above
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    record = next(row for item, row in mastery_rows if item.id == concept.id)
    mistakes = mistake_counts.get(concept.id, 0)
    documents = crud.list_documents_for_thread(db, project.id)

    reasons = []
    if mistakes:
        reasons.append(f"{mistakes} of your last {REPEATED_MISTAKE_WINDOW} answers scored below 60")
    reasons.append(f"mastery is the lowest in this project at {round(record.mastery_score)}%")
    if difficulty == "easy":
        reasons.append("difficulty eased to rebuild the fundamentals")
    elif difficulty == "hard":
        reasons.append("difficulty raised because this is already strong")

    return {
        "project_id": project.id,
        "concept": concept.name,
        "concept_id": concept.id,
        "difficulty": difficulty,
        "mastery_score": round(record.mastery_score, 2),
        "attempts": record.attempt_count,
        "recent_mistakes": mistakes,
        "reason": "; ".join(reasons),
        "document_id": documents[0].id if documents else None,
        "document_name": documents[0].filename if documents else None,
        "has_material": bool(documents),
    }


# ---------------------------------------------------------------------------
# Adaptive quiz → mastery evidence
# ---------------------------------------------------------------------------

@router.post("/quiz-result", response_model=QuizResultResponse)
def record_quiz_result(
    payload: QuizResultRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    db: Annotated[Session, Depends(get_db)],
) -> QuizResultResponse:
    """Record adaptive quiz answers as concept-mastery evidence.

    Multiple-choice practice is real evidence of understanding, so a quiz now
    moves mastery exactly like an open-ended assessment does — with a smaller
    weight only in the sense that a single quiz can contain many items. Each
    answered question contributes one evidence point to the concept's EMA.
    """
    project = _owned_project(db, payload.project_id, current_user)
    correct = sum(1 for item in payload.results if item.correct)
    total = len(payload.results)
    score = round(100.0 * correct / total, 2)
    concept_name = (payload.concept or payload.topic).strip()

    concept = resolve_concept(db, project_id=project.id, name=concept_name, embeddings=embeddings)

    # One evidence point per quiz session keeps the mastery timeline readable:
    # growth analysis compares whole practice sessions, not individual options.
    update_concept_mastery(
        db,
        user_id=current_user.id,
        project_id=project.id,
        concept_id=concept.id,
        evidence_score=score,
        event_key=f"quiz:{project.id}:{concept.id}:{uuid4()}",
    )

    if payload.document_id:
        crud.create_quiz_attempt(
            db,
            user_id=current_user.id,
            document_id=payload.document_id,
            topic=payload.topic,
            correct_count=correct,
            total_questions=total,
        )

    crud.log_event(
        db,
        event_key=f"quiz:{project.id}:{uuid4()}:summary",
        user_id=current_user.id,
        project_id=project.id,
        event_type="quiz_attempted",
        payload_json=json.dumps(
            {"concept": concept.name, "topic": payload.topic, "correct": correct, "total": total, "score": score}
        ),
    )
    # Keep the factual study record in step with the new mastery evidence so the
    # Progress workspace and the Tutor's memory stay consistent.
    record_studied_topic(db, current_user.id, payload.topic, payload.document_id)
    if score < 60:
        record_weak_topic(
            db,
            current_user.id,
            payload.topic,
            f"scored {correct}/{total} on {payload.topic}",
            payload.document_id,
            reason="quiz_score",
        )

    recommendations = refresh_recommendations(db, user_id=current_user.id, project_id=project.id)
    return QuizResultResponse(
        answered=total,
        correct=correct,
        score=score,
        mastery=_snapshot(
            db, user_id=current_user.id, project_id=project.id, concept_id=concept.id, concept_name=concept.name
        ),
        recommendations=[
            {"id": row.id, "text": row.recommendation, "trigger": row.trigger} for row in recommendations
        ],
    )


# ---------------------------------------------------------------------------
# Open-ended assessment
# ---------------------------------------------------------------------------

@router.post("/assessment/generate", response_model=AssessmentGenerateResponse)
def generate_assessment(
    payload: AssessmentGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    llm: Annotated[BaseChatModel, Depends(get_llm)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    db: Annotated[Session, Depends(get_db)],
) -> AssessmentGenerateResponse:
    """Generate grounded explanation-style questions for one concept."""
    project = _owned_project(db, payload.project_id, current_user)
    document = _project_document(db, project.id, payload.document_id)
    context, citation_hint = _retrieve_evidence(document, payload.concept, embeddings)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Upload course material for this project before generating an assessment.",
        )
    try:
        raw_questions = generate_open_ended_questions(
            llm,
            concept=payload.concept,
            difficulty=payload.difficulty,
            num_questions=payload.num_questions,
            context=context,
            citation_hint=citation_hint,
        )
    except AssessmentGenerationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    return AssessmentGenerateResponse(
        project_id=project.id,
        concept=payload.concept,
        difficulty=payload.difficulty,
        grounded=True,
        questions=[
            AssessmentQuestion(
                id=str(uuid4()),
                question=item["question"],
                reference_answer=item["reference_answer"],
                rubric=item["rubric"] or RUBRIC,
                source_citation=item["source_citation"] or citation_hint,
            )
            for item in raw_questions
        ],
    )


@router.post("/assessment/grade", response_model=AssessmentGradeResponse)
def grade_assessment(
    payload: AssessmentGradeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    llm: Annotated[BaseChatModel, Depends(get_llm)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    db: Annotated[Session, Depends(get_db)],
) -> AssessmentGradeResponse:
    """Grade one open-ended answer, persist it, and move the mastery estimate."""
    project = _owned_project(db, payload.project_id, current_user)
    document = _project_document(db, project.id, payload.document_id)
    context, _ = _retrieve_evidence(document, payload.question, embeddings)

    try:
        grade = grade_open_ended_answer(
            llm,
            question=payload.question,
            answer=payload.answer,
            reference_answer=payload.reference_answer or "(no reference provided)",
            retrieved_context=context or "(no retrieved evidence available)",
            rubric=payload.rubric or RUBRIC,
        )
    except GradingError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    concept = resolve_concept(db, project_id=project.id, name=payload.concept, embeddings=embeddings)
    overall = grade.overall_score

    attempt = AssessmentAttempt(
        user_id=current_user.id,
        project_id=project.id,
        concept_id=concept.id,
        question=payload.question,
        answer=payload.answer,
        understanding=grade.understanding,
        accuracy=grade.accuracy,
        concepts_covered_json=json.dumps(grade.concepts_covered),
        concepts_missing_json=json.dumps(grade.concepts_missing),
        overall_score=overall,
        created_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    update_concept_mastery(
        db,
        user_id=current_user.id,
        project_id=project.id,
        concept_id=concept.id,
        evidence_score=overall,
        event_key=f"assessment:{project.id}:{concept.id}:{uuid4()}",
    )
    crud.log_event(
        db,
        event_key=f"assessment:{project.id}:{uuid4()}:completed",
        user_id=current_user.id,
        project_id=project.id,
        event_type="assessment_completed",
        payload_json=json.dumps(
            {
                "attempt_id": attempt.id,
                "concept": concept.name,
                "overall_score": overall,
                "understanding": grade.understanding,
                "accuracy": grade.accuracy,
                "feedback": grade.feedback,
                "concepts_missing": grade.concepts_missing,
            }
        ),
    )

    if overall < 60:
        record_weak_topic(
            db,
            current_user.id,
            payload.concept,
            f"scored {overall:.0f}/100 on an open-ended question about {payload.concept}",
            payload.document_id,
            reason="assessment_score",
        )

    recommendations = refresh_recommendations(db, user_id=current_user.id, project_id=project.id)
    return AssessmentGradeResponse(
        understanding=grade.understanding,
        accuracy=grade.accuracy,
        overall_score=overall,
        concepts_covered=grade.concepts_covered,
        concepts_missing=grade.concepts_missing,
        feedback=grade.feedback,
        mastery=_snapshot(
            db, user_id=current_user.id, project_id=project.id, concept_id=concept.id, concept_name=concept.name
        ),
        assessment_average=_average_assessment_score(db, current_user.id, project.id),
        recommendations=[
            {"id": row.id, "text": row.recommendation, "trigger": row.trigger} for row in recommendations
        ],
    )


@router.get("/assessment/{project_id}", response_model=AssessmentSummaryResponse)
def assessment_summary(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AssessmentSummaryResponse:
    """Graded answers, per-concept growth and the next steps for one project."""
    project = _owned_project(db, project_id, current_user)
    mastery_rows = crud.list_mastery_for_user_and_project(db, current_user.id, project.id)
    history_by_concept = mastery_history_by_concept(db, user_id=current_user.id, project_id=project.id)

    growth = []
    for concept, record in mastery_rows:
        points = history_by_concept.get(concept.id, [])
        summary = summarize_concept_growth(points)
        growth.append(
            ConceptGrowth(
                concept=concept.name,
                concept_id=concept.id,
                score=round(record.mastery_score, 2),
                attempts=record.attempt_count,
                classification=summary["classification"],
                delta=summary["delta"],
                samples=summary["samples"],
                history=points,
            )
        )

    concepts = {concept.id: concept.name for concept in crud.list_concepts_for_project(db, project.id)}
    attempts = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.user_id == current_user.id, AssessmentAttempt.project_id == project.id)
        .order_by(AssessmentAttempt.created_at.desc())
        .limit(50)
        .all()
    )
    feedback_by_attempt = _feedback_index(db, project.id, current_user.id)

    scores = [row.score for row in growth]
    return AssessmentSummaryResponse(
        project_id=project.id,
        assessment_average=_average_assessment_score(db, current_user.id, project.id),
        graded_count=len(attempts),
        overall_progress=round(sum(scores) / len(scores), 2) if scores else None,
        growth=growth,
        history=[
            AssessmentHistoryItem(
                id=row.id,
                concept=concepts.get(row.concept_id or ""),
                question=row.question,
                answer=row.answer,
                understanding=row.understanding,
                accuracy=row.accuracy,
                overall_score=row.overall_score,
                feedback=feedback_by_attempt.get(row.id, ""),
                created_at=row.created_at,
            )
            for row in attempts
        ],
        recommendations=[
            {"id": row.id, "text": row.recommendation, "trigger": row.trigger}
            for row in crud.list_active_recommendations_for_project(db, current_user.id, project.id)
        ],
    )


def _feedback_index(db: Session, project_id: str, user_id: str) -> dict[int, str]:
    """Map assessment attempt ids to the feedback text captured in their audit event."""
    index: dict[int, str] = {}
    for event in crud.list_events_for_project(db, project_id, limit=400):
        if event.event_type != "assessment_completed" or event.user_id != user_id:
            continue
        try:
            payload = json.loads(event.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        attempt_id = payload.get("attempt_id")
        feedback = payload.get("feedback")
        if isinstance(attempt_id, int) and feedback:
            index[attempt_id] = feedback
    return index


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

@router.get("/recommendations/{project_id}")
def list_recommendations(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """Active next steps for a project, refreshed from current evidence."""
    project = _owned_project(db, project_id, current_user)
    rows = refresh_recommendations(db, user_id=current_user.id, project_id=project.id)
    return [
        {"id": row.id, "text": row.recommendation, "trigger": row.trigger, "concept_id": row.concept_id}
        for row in rows
    ]


@router.post("/recommendations/{recommendation_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_recommendation(
    recommendation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Hide a recommendation the learner has already acted on."""
    if crud.dismiss_recommendation(db, recommendation_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found.")
