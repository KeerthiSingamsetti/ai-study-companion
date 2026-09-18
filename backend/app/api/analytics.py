"""Separate learner, project, global, and admin operational analytics views."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin_user, get_current_user
from app.db import crud
from app.db.models import AICallLog, AssessmentAttempt, Concept, ConceptMastery, Document, Event, IngestionJob, Recommendation, Thread, User
from app.db.session import get_db
from app.services.learning import mastery_history_by_concept, refresh_recommendations, summarize_concept_growth

router = APIRouter(prefix="/analytics", tags=["analytics"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


def _event(event: Event) -> dict:
    try:
        payload = json.loads(event.payload_json)
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return {"id": event.id, "type": event.event_type, "project_id": event.project_id,
            "payload": payload, "created_at": event.created_at}


@router.get("/home")
def home_dashboard(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    """Personal home view: recent activity, workload, and recommended next action."""
    projects = crud.list_threads(db, user_id=current_user.id)
    recommendations = (db.query(Recommendation).filter(Recommendation.user_id == current_user.id,
                       Recommendation.is_dismissed.is_(False)).order_by(Recommendation.created_at.desc()).limit(5).all())
    concept_rows = db.query(Concept).join(Thread, Concept.project_id == Thread.id).filter(Thread.user_id == current_user.id).all()
    return {
        "projects_count": len(projects),
        "documents_count": db.query(Document).join(Thread, Document.thread_id == Thread.id).filter(Thread.user_id == current_user.id).count(),
        "concepts_count": len(concept_rows),
        "recent_activity": [_event(item) for item in crud.list_events_for_user(db, current_user.id, limit=10)],
        "recommendations": [{"id": item.id, "text": item.recommendation, "trigger": item.trigger,
                               "project_id": item.project_id} for item in recommendations],
        "projects": [{"id": p.id, "title": p.title, "updated_at": p.updated_at} for p in projects[:8]],
    }


def _concept_growth(db: Session, *, user_id: str, project_id: str) -> tuple[list[dict], float | None]:
    """Per-concept mastery with its improving/stable/needs-attention classification."""
    history = mastery_history_by_concept(db, user_id=user_id, project_id=project_id)
    rows = []
    for concept, record in crud.list_mastery_for_user_and_project(db, user_id, project_id):
        points = history.get(concept.id, [])
        summary = summarize_concept_growth(points)
        rows.append({
            "concept_id": concept.id,
            "concept": concept.name,
            "score": round(record.mastery_score, 2),
            "attempts": record.attempt_count,
            "classification": summary["classification"],
            "delta": summary["delta"],
            "samples": summary["samples"],
            "last_updated": record.last_updated,
            "history": points,
        })
    scores = [row["score"] for row in rows]
    return rows, (round(sum(scores) / len(scores), 2) if scores else None)


@router.get("/projects/{project_id}")
def project_analytics(project_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    """Project learning state: progress, concepts, growth, activity and next step."""
    project = crud.get_thread(db, project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    jobs = crud.list_ingestion_jobs_for_project(db, project_id)
    assessments = db.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == current_user.id,
                                                       AssessmentAttempt.project_id == project_id).all()
    mastery, overall_progress = _concept_growth(db, user_id=current_user.id, project_id=project_id)
    recommendations = refresh_recommendations(db, user_id=current_user.id, project_id=project_id)
    activity = [_event(item) for item in crud.list_events_for_project(db, project_id, limit=30)]
    return {
        "project": {"id": project.id, "title": project.title, "created_at": project.created_at,
                     "description": project.description, "learning_goal": project.learning_goal},
        "documents": db.query(Document).filter(Document.thread_id == project_id).count(),
        "ingestion": [{"id": j.id, "document_id": j.document_id, "status": j.status, "retry_count": j.retry_count,
                        "error_msg": j.error_msg} for j in jobs],
        "mastery": mastery,
        "overall_progress": overall_progress,
        "assessment_average": round(sum(a.overall_score for a in assessments) / len(assessments), 2) if assessments else None,
        "assessments_graded": len(assessments),
        "recommendations": [{"id": row.id, "text": row.recommendation, "trigger": row.trigger,
                              "concept_id": row.concept_id} for row in recommendations],
        "latest_activity": activity[0] if activity else None,
        "activity": activity,
    }


@router.get("/spaces/{space_id}")
def space_analytics(space_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    """Space-level view: projects, activity, progress and areas requiring attention."""
    space = crud.get_space(db, space_id, user_id=current_user.id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found.")
    projects = crud.list_threads(db, user_id=current_user.id, space_id=space_id)
    project_rows = []
    attention: list[dict] = []
    scores: list[float] = []
    documents_count = 0

    all_events = crud.list_events_for_user(db, current_user.id, limit=100)
    project_ids = {project.id for project in projects}
    latest_event_by_project: dict[str, Any] = {}
    for item in all_events:
        if item.project_id in project_ids and item.project_id not in latest_event_by_project:
            latest_event_by_project[item.project_id] = item

    for project in projects:
        mastery, progress = _concept_growth(db, user_id=current_user.id, project_id=project.id)
        documents_count += db.query(Document).filter(Document.thread_id == project.id).count()
        if progress is not None:
            scores.append(progress)
        weakest = min(mastery, key=lambda row: row["score"], default=None)
        latest = latest_event_by_project.get(project.id)
        project_rows.append({
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "learning_goal": project.learning_goal,
            "updated_at": project.updated_at,
            "documents": db.query(Document).filter(Document.thread_id == project.id).count(),
            "concepts_tracked": len(mastery),
            "overall_progress": progress,
            "weakest_concept": weakest["concept"] if weakest else None,
            "latest_activity": _event(latest) if latest is not None else None,
        })
        for row in mastery:
            if row["classification"] == "needs_attention":
                attention.append({"concept": row["concept"], "score": row["score"], "project_id": project.id,
                                  "project_title": project.title, "classification": row["classification"]})

    attention.sort(key=lambda row: row["score"])
    return {
        "space": {"id": space.id, "name": space.name, "description": space.description,
                  "accent": space.accent, "icon": space.icon, "created_at": space.created_at},
        "projects_count": len(projects),
        "documents_count": documents_count,
        "overall_progress": round(sum(scores) / len(scores), 2) if scores else None,
        "projects": project_rows,
        "areas_requiring_attention": attention[:6],
        "activity": [_event(item) for item in all_events if item.project_id in project_ids][:12],
    }


@router.get("/global")
def global_analytics(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    """Cross-project learner trends without exposing another user's data."""
    since = datetime.now(timezone.utc) - timedelta(days=7)
    events = db.query(Event).filter(Event.user_id == current_user.id, Event.created_at >= since).all()
    counts: dict[str, int] = {}
    for event in events:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1
    calls = db.query(AICallLog).filter(AICallLog.user_id == current_user.id).all()
    return {"period_days": 7, "activity_by_type": counts,
            "ai_calls": len(calls), "ai_success_rate": round(100 * sum(c.success for c in calls) / len(calls), 1) if calls else None,
            "projects": len(crud.list_threads(db, user_id=current_user.id))}


@router.get("/projects/{project_id}/retrieval-traces")
def retrieval_traces(project_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    if crud.get_thread(db, project_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    output = []
    for trace in crud.list_retrieval_traces(db, project_id):
        output.append({"id": trace.id, "ai_call_id": trace.ai_call_id, "query": trace.query, "strategy": trace.strategy,
                       "threshold": trace.threshold, "selected_count": trace.selected_count, "grounded": trace.grounded,
                       "chunks": json.loads(trace.chunks_json), "created_at": trace.created_at})
    return output


@admin_router.get("/operations")
def admin_operations(admin: Annotated[User, Depends(get_current_admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    """Operational admin view: job health and model reliability."""
    del admin
    jobs = db.query(IngestionJob).all()
    calls = db.query(AICallLog).all()
    return {"ingestion": {state: sum(j.status == state for j in jobs) for state in ("queued", "processing", "ready", "failed")},
            "ai_calls": {"total": len(calls), "failed": sum(not c.success for c in calls),
                         "avg_latency_ms": round(sum(c.latency_ms for c in calls) / len(calls), 1) if calls else 0},
            "users": db.query(User).count()}


@admin_router.get("/product")
def admin_product(admin: Annotated[User, Depends(get_current_admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    """Product admin view: adoption and learning-loop event distribution."""
    del admin
    rows = db.query(Event.event_type, func.count(Event.id)).group_by(Event.event_type).all()
    return {"event_counts": dict(rows), "projects": db.query(Document.thread_id).distinct().count(),
            "documents": db.query(Document).count()}


@admin_router.get("/users/{user_id}")
def admin_user_inspector(
    user_id: str,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Inspect one user's learning journey: spaces, projects, activity,
    assessments, mastery, progress records and AI usage. Read-only."""
    del admin
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    spaces = crud.list_spaces_for_user(db, user_id=user_id)
    projects = db.query(Thread).filter(Thread.user_id == user_id).order_by(Thread.updated_at.desc()).all()
    project_ids = [p.id for p in projects]

    events = (
        db.query(Event)
        .filter(Event.user_id == user_id)
        .order_by(Event.created_at.desc())
        .limit(30)
        .all()
    )

    assessments = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.user_id == user_id)
        .order_by(AssessmentAttempt.created_at.desc())
        .limit(10)
        .all()
    )
    if project_ids:
        mastery = (
            db.query(ConceptMastery)
            .join(Concept, Concept.id == ConceptMastery.concept_id)
            .filter(Concept.project_id.in_(project_ids))
            .order_by(ConceptMastery.mastery_score.asc())
            .limit(12)
            .all()
        )
        concept_names = {c.id: c.name for c in db.query(Concept).filter(Concept.project_id.in_(project_ids)).all()}
    else:
        mastery, concept_names = [], {}

    calls = (
        db.query(AICallLog)
        .filter(AICallLog.user_id == user_id)
        .order_by(AICallLog.created_at.desc())
        .limit(200)
        .all()
    )

    return {
        "user": {"id": user.id, "email": user.email, "display_name": user.display_name,
                 "role": user.role, "created_at": user.created_at},
        "spaces": [{"id": s.id, "name": s.name, "description": s.description} for s in spaces],
        "projects": [{"id": p.id, "title": p.title, "space_id": p.space_id,
                      "learning_goal": p.learning_goal, "updated_at": p.updated_at} for p in projects],
        "activity": [_event(e) for e in events],
        "assessments": [{"id": a.id, "project_id": a.project_id, "question": a.question,
                         "understanding": a.understanding, "accuracy": a.accuracy,
                         "created_at": a.created_at} for a in assessments],
        "mastery": [{"concept": concept_names.get(m.concept_id, m.concept_id), "score": m.mastery_score,
                     "attempts": m.attempt_count} for m in mastery],
        "ai_usage": {
            "calls": len(calls),
            "failed": sum(not c.success for c in calls),
            "avg_latency_ms": round(sum(c.latency_ms for c in calls) / len(calls), 1) if calls else 0,
            "estimated_cost_usd": round(sum(c.estimated_cost_usd for c in calls), 4),
            "by_feature": {},
        },
    }


@admin_router.get("/activity")
def admin_platform_activity(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
    user_id: str | None = None,
    space_id: str | None = None,
    project_id: str | None = None,
    event_type: str | None = None,
    days: int = 30,
) -> list[dict]:
    """Platform-wide activity feed, filterable by user, Space, Project, event
    type and time period (lightweight operational analytics, not monitoring)."""
    del admin
    days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = db.query(Event).filter(Event.created_at >= since)
    if user_id:
        query = query.filter(Event.user_id == user_id)
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if project_id:
        query = query.filter(Event.project_id == project_id)
    elif space_id:
        project_ids = [
            row[0]
            for row in db.query(Thread.id).filter(Thread.space_id == space_id).all()
        ]
        query = query.filter(Event.project_id.in_(project_ids or ["__none__"]))

    rows = query.order_by(Event.created_at.desc()).limit(100).all()
    if not rows:
        return []

    users = {u.id: u.display_name for u in db.query(User).filter(User.id.in_({r.user_id for r in rows})).all()}
    projects = {p.id: p.title for p in db.query(Thread).filter(Thread.id.in_({r.project_id for r in rows if r.project_id})).all()}
    return [
        {**_event(row), "user": users.get(row.user_id, row.user_id), "user_id": row.user_id,
         "project": projects.get(row.project_id) if row.project_id else None}
        for row in rows
    ]


@admin_router.get("/activity/types")
def admin_activity_types(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[str]:
    """Distinct event types, for the platform-activity filter dropdown."""
    del admin
    return [row[0] for row in db.query(Event.event_type).distinct().order_by(Event.event_type).all()]
