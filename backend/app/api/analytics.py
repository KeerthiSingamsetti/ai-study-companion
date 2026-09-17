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
from app.db.models import AICallLog, AssessmentAttempt, Document, Event, IngestionJob, Recommendation, Thread, User
from app.db.session import get_db

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
    return {
        "projects_count": len(projects),
        "documents_count": db.query(Document).join(Thread, Document.thread_id == Thread.id).filter(Thread.user_id == current_user.id).count(),
        "recent_activity": [_event(item) for item in crud.list_events_for_user(db, current_user.id, limit=10)],
        "recommendations": [{"id": item.id, "text": item.recommendation, "trigger": item.trigger,
                               "project_id": item.project_id} for item in recommendations],
        "projects": [{"id": p.id, "title": p.title, "updated_at": p.updated_at} for p in projects[:8]],
    }


@router.get("/projects/{project_id}")
def project_analytics(project_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    """Project-specific learning and content health, distinct from the home view."""
    project = crud.get_thread(db, project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    mastery = crud.list_mastery_for_user_and_project(db, current_user.id, project_id)
    jobs = crud.list_ingestion_jobs_for_project(db, project_id)
    assessments = db.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == current_user.id,
                                                       AssessmentAttempt.project_id == project_id).all()
    return {
        "project": {"id": project.id, "title": project.title, "created_at": project.created_at},
        "documents": db.query(Document).filter(Document.thread_id == project_id).count(),
        "ingestion": [{"id": j.id, "document_id": j.document_id, "status": j.status, "retry_count": j.retry_count,
                        "error_msg": j.error_msg} for j in jobs],
        "mastery": [{"concept": concept.name, "score": record.mastery_score, "attempts": record.attempt_count}
                    for concept, record in mastery],
        "assessment_average": round(sum(a.overall_score for a in assessments) / len(assessments), 2) if assessments else None,
        "activity": [_event(item) for item in crud.list_events_for_project(db, project_id, limit=30)],
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
