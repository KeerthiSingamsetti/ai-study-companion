"""Dedicated admin API: platform oversight for inspection-role administrators.

The PRD frames the admin role as platform oversight (Section 16 uses only
inspect/view/filter verbs), so these endpoints expose read-only aggregates
over the same records the product already writes. No endpoint here creates
or mutates product state.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin_user
from app.db import crud
from app.db.models import (
    AICallLog,
    AssessmentAttempt,
    Concept,
    ConceptMastery,
    Document,
    Event,
    IngestionJob,
    RetrievalTrace,
    Space,
    Thread,
    User,
)
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin-v2"])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _user_brief(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "created_at": _iso(user.created_at),
    }


def _project_brief(project: Thread, counts: dict[str, int]) -> dict[str, Any]:
    return {
        "id": project.id,
        "title": project.title,
        "user_id": project.user_id,
        "space_id": project.space_id,
        "description": project.description,
        "learning_goal": project.learning_goal,
        "created_at": _iso(project.created_at),
        "updated_at": _iso(project.updated_at),
        "documents": counts.get(project.id, 0),
    }


# ── Platform overview ─────────────────────────────────────────────────────


@router.get("/overview")
def admin_overview(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Single platform health snapshot: accounts, projects, jobs, AI layer."""
    del admin
    jobs = db.query(IngestionJob).all()
    calls = db.query(AICallLog).all()
    return {
        "users": db.query(User).count(),
        "spaces": db.query(Space).count(),
        "projects": db.query(Thread).count(),
        "documents": db.query(Document).count(),
        "ingestion": {
            state: sum(job.status == state for job in jobs)
            for state in ("queued", "processing", "ready", "failed")
        },
        "ai_calls": {
            "total": len(calls),
            "failed": sum(not call.success for call in calls),
            "avg_latency_ms": round(sum(call.latency_ms for call in calls) / len(calls), 1) if calls else 0,
            "estimated_cost_usd": round(sum(call.estimated_cost_usd for call in calls), 4),
        },
    }


# ── Users ─────────────────────────────────────────────────────────────────


@router.get("/users")
def admin_list_users(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """All accounts with per-user activity rollups, optionally searched."""
    del admin
    limit = max(1, min(limit, 200))
    query = db.query(User)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (func.lower(User.email).like(like)) | (func.lower(User.display_name).like(like))
        )
    users = query.order_by(User.created_at.desc()).limit(limit).all()

    since = datetime.now(timezone.utc) - timedelta(days=30)
    active_counts = dict(
        db.query(Event.user_id, func.count(func.distinct(Event.project_id)))
        .filter(Event.created_at >= since)
        .group_by(Event.user_id)
        .all()
    )
    project_counts = dict(db.query(Thread.user_id, func.count(Thread.id)).group_by(Thread.user_id).all())
    space_counts = dict(db.query(Space.user_id, func.count(Space.id)).group_by(Space.user_id).all())
    call_counts = dict(db.query(AICallLog.user_id, func.count(AICallLog.id)).group_by(AICallLog.user_id).all())

    return {
        "users": [
            {
                **_user_brief(user),
                "spaces_count": space_counts.get(user.id, 0),
                "projects_count": project_counts.get(user.id, 0),
                "active_projects_30d": active_counts.get(user.id, 0),
                "ai_calls": call_counts.get(user.id, 0),
            }
            for user in users
        ],
        "total": db.query(func.count(User.id)).scalar(),
    }


@router.get("/users/{user_id}")
def admin_user_inspector(
    user_id: str,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Inspect one user's learning journey: spaces, projects, activity,
    assessments, mastery, progress records and AI usage. Read-only."""
    del admin
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    spaces = crud.list_spaces_for_user(db, user_id=user_id)
    projects = db.query(Thread).filter(Thread.user_id == user_id).order_by(Thread.updated_at.desc()).all()
    project_ids = [project.id for project in projects]

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
        concept_names = {
            concept.id: concept.name
            for concept in db.query(Concept).filter(Concept.project_id.in_(project_ids)).all()
        }
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
        "user": _user_brief(user),
        "spaces": [{"id": space.id, "name": space.name, "description": space.description} for space in spaces],
        "projects": [
            {
                "id": project.id,
                "title": project.title,
                "space_id": project.space_id,
                "learning_goal": project.learning_goal,
                "updated_at": _iso(project.updated_at),
            }
            for project in projects
        ],
        "activity": [
            {
                "id": event.id,
                "type": event.event_type,
                "project_id": event.project_id,
                "created_at": _iso(event.created_at),
            }
            for event in events
        ],
        "assessments": [
            {
                "id": attempt.id,
                "project_id": attempt.project_id,
                "question": attempt.question,
                "understanding": attempt.understanding,
                "accuracy": attempt.accuracy,
                "created_at": _iso(attempt.created_at),
            }
            for attempt in assessments
        ],
        "mastery": [
            {
                "concept": concept_names.get(row.concept_id, row.concept_id),
                "score": row.mastery_score,
                "attempts": row.attempt_count,
            }
            for row in mastery
        ],
        "ai_usage": {
            "calls": len(calls),
            "failed": sum(not call.success for call in calls),
            "avg_latency_ms": round(sum(call.latency_ms for call in calls) / len(calls), 1) if calls else 0,
            "estimated_cost_usd": round(sum(call.estimated_cost_usd for call in calls), 4),
            "by_feature": {},
        },
    }


# ── Spaces & Projects ─────────────────────────────────────────────────────


@router.get("/spaces")
def admin_list_spaces(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """All Spaces platform-wide with owner and project counts."""
    del admin
    owners = {user.id: user.display_name for user in db.query(User).all()}
    project_counts = dict(
        db.query(Thread.space_id, func.count(Thread.id)).group_by(Thread.space_id).all()
    )
    spaces = db.query(Space).order_by(Space.created_at.desc()).all()
    return {
        "spaces": [
            {
                "id": space.id,
                "name": space.name,
                "description": space.description,
                "accent": space.accent,
                "owner": owners.get(space.user_id, space.user_id),
                "projects_count": project_counts.get(space.id, 0),
                "created_at": _iso(space.created_at),
            }
            for space in spaces
        ],
        "total": len(spaces),
    }


@router.get("/projects")
def admin_list_projects(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
    space_id: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """All Projects platform-wide, filterable by Space or owner."""
    del admin
    limit = max(1, min(limit, 200))
    query = db.query(Thread)
    if space_id:
        query = query.filter(Thread.space_id == space_id)
    if user_id:
        query = query.filter(Thread.user_id == user_id)
    projects = query.order_by(Thread.updated_at.desc()).limit(limit).all()

    document_counts = dict(
        db.query(Document.thread_id, func.count(Document.id)).group_by(Document.thread_id).all()
    )
    owners = {user.id: user.display_name for user in db.query(User).all()}
    space_names = {space.id: space.name for space in db.query(Space).all()}

    return {
        "projects": [_project_brief(project, document_counts) for project in projects],
        "owners": owners,
        "space_names": space_names,
        "total": db.query(func.count(Thread.id)).scalar(),
    }


# ── AI usage ──────────────────────────────────────────────────────────────


@router.get("/ai-usage")
def admin_ai_usage(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
    days: int = 30,
) -> dict[str, Any]:
    """AI spend and reliability broken down by feature and by model."""
    del admin
    days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    calls = db.query(AICallLog).filter(AICallLog.created_at >= since).all()

    by_feature: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    for call in calls:
        for bucket, key in ((by_feature, call.feature), (by_model, call.model)):
            entry = bucket.setdefault(
                key,
                {"calls": 0, "failed": 0, "latency_ms": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            )
            entry["calls"] += 1
            entry["failed"] += not call.success
            entry["latency_ms"] += call.latency_ms
            entry["input_tokens"] += call.input_tokens
            entry["output_tokens"] += call.output_tokens
            entry["cost_usd"] += call.estimated_cost_usd

    def _finish(entries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for name, entry in entries.items():
            rows.append(
                {
                    # Historical rows predate the model being recorded on every
                    # call; label them honestly instead of leaking a null.
                    "name": name or "unattributed",
                    "calls": entry["calls"],
                    "failed": entry["failed"],
                    "avg_latency_ms": round(entry["latency_ms"] / entry["calls"], 1),
                    "input_tokens": entry["input_tokens"],
                    "output_tokens": entry["output_tokens"],
                    "cost_usd": round(entry["cost_usd"], 4),
                }
            )
        return sorted(rows, key=lambda row: row["calls"], reverse=True)

    return {
        "period_days": days,
        "total_calls": len(calls),
        "total_failed": sum(not call.success for call in calls),
        "total_cost_usd": round(sum(call.estimated_cost_usd for call in calls), 4),
        "by_feature": _finish(by_feature),
        "by_model": _finish(by_model),
    }


# ── AI evaluation ─────────────────────────────────────────────────────────


@router.get("/evaluation")
def admin_evaluation(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Evaluation summary plus live groundedness signals from real traffic:
    retrieval traces and refusal rates. Read-only, no scoring of content."""
    del admin
    traces = db.query(RetrievalTrace).order_by(RetrievalTrace.created_at.desc()).limit(200).all()
    grounded_count = sum(bool(trace.grounded) for trace in traces)

    tutor_calls = (
        db.query(AICallLog)
        .filter(AICallLog.feature == "tutor")
        .order_by(AICallLog.created_at.desc())
        .limit(200)
        .all()
    )

    # Groundedness must come from live data only. The curated eval runner is a
    # development-time artifact (backend/eval) and is intentionally NOT reported
    # here as if it were fresh production telemetry.
    return {
        "retrieval": {
            "traces_window": len(traces),
            "grounded": grounded_count,
            "grounded_rate": round(100 * grounded_count / len(traces), 1) if traces else None,
        },
        "tutor_calls": {
            "window": len(tutor_calls),
            "failed": sum(not call.success for call in tutor_calls),
            "avg_latency_ms": round(sum(call.latency_ms for call in tutor_calls) / len(tutor_calls), 1)
            if tutor_calls
            else 0,
        },
        "note": "Live groundedness comes from recorded retrieval traces; the curated evaluation suite runs offline via backend/eval.",
    }


# ── Background jobs ───────────────────────────────────────────────────────


@router.get("/jobs")
def admin_jobs(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
) -> dict[str, Any]:
    """Ingestion pipeline jobs with per-job document context."""
    del admin
    query = db.query(IngestionJob)
    if status:
        query = query.filter(IngestionJob.status == status)
    jobs = query.order_by(IngestionJob.created_at.desc()).limit(100).all()
    filenames = {
        document.id: document.filename
        for document in db.query(Document).filter(Document.id.in_({job.document_id for job in jobs})).all()
    } if jobs else {}
    return {
        "jobs": [
            {
                "id": job.id,
                "document_id": job.document_id,
                "document_filename": filenames.get(job.document_id),
                "status": job.status,
                "retry_count": job.retry_count,
                "error": job.error_msg,
                "created_at": _iso(job.created_at),
                "updated_at": _iso(job.updated_at),
            }
            for job in jobs
        ],
        "states": {
            state: db.query(func.count(IngestionJob.id)).filter(IngestionJob.status == state).scalar()
            for state in ("queued", "processing", "ready", "failed")
        },
    }


# ── System health ─────────────────────────────────────────────────────────


@router.get("/health")
def admin_health(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Lightweight operational health: DB reachable, recent AI reliability."""
    del admin
    db.execute(func.count(User.id).select())
    recent_calls = (
        db.query(AICallLog)
        .filter(AICallLog.created_at >= datetime.now(timezone.utc) - timedelta(hours=24))
        .all()
    )
    return {
        "database": "reachable",
        "ai_calls_24h": len(recent_calls),
        "ai_failed_24h": sum(not call.success for call in recent_calls),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Activity feed (platform-wide, filterable) ─────────────────────────────


@router.get("/activity")
def admin_platform_activity(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
    user_id: str | None = None,
    space_id: str | None = None,
    project_id: str | None = None,
    event_type: str | None = None,
    days: int = 30,
) -> list[dict[str, Any]]:
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
            row[0] for row in db.query(Thread.id).filter(Thread.space_id == space_id).all()
        ]
        query = query.filter(Event.project_id.in_(project_ids or ["__none__"]))

    rows = query.order_by(Event.created_at.desc()).limit(100).all()
    if not rows:
        return []

    users = {
        user.id: user.display_name
        for user in db.query(User).filter(User.id.in_({row.user_id for row in rows})).all()
    }
    projects = {
        project.id: project.title
        for project in db.query(Thread)
        .filter(Thread.id.in_({row.project_id for row in rows if row.project_id}))
        .all()
    }
    return [
        {
            "id": row.id,
            "type": row.event_type,
            "payload": {},
            "project_id": row.project_id,
            "user": users.get(row.user_id, row.user_id),
            "user_id": row.user_id,
            "project": projects.get(row.project_id) if row.project_id else None,
            "created_at": _iso(row.created_at),
        }
        for row in rows
    ]


@router.get("/activity/types")
def admin_activity_types(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[str]:
    """Distinct event types, for the platform-activity filter dropdown."""
    del admin
    return [row[0] for row in db.query(Event.event_type).distinct().order_by(Event.event_type).all()]


@router.get("/activity/filters")
def admin_activity_filter_options(
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[Session, Depends(get_db)],
    user_id: str | None = None,
) -> dict[str, Any]:
    """Id/label options for the activity feed's user and Project pickers.

    Operators filter by choosing an account or a Project by name — the raw
    identifiers are never something an administrator should have to type.
    Project options narrow to the selected account so the picker stays short,
    and default to Projects that actually have recorded activity.
    """
    del admin
    space_names = {space.id: space.name for space in db.query(Space).all()}
    latest = dict(db.query(Event.project_id, func.max(Event.created_at)).group_by(Event.project_id).all())

    # Only accounts with recorded events are offered: any other account would
    # filter the feed down to nothing. The selected account stays in the list.
    active_user_ids = {row[0] for row in db.query(Event.user_id).distinct().all() if row[0]}
    if user_id:
        active_user_ids.add(user_id)
    users = (
        db.query(User)
        .filter(User.id.in_(active_user_ids or {"__none__"}))
        .order_by(User.display_name)
        .all()
    )

    project_query = db.query(Thread)
    if user_id:
        project_query = project_query.filter(Thread.user_id == user_id)
    else:
        project_query = project_query.filter(Thread.id.in_({pid for pid in latest if pid} or {"__none__"}))
    # Most recently active first, so the picker opens on what matters.
    projects = sorted(
        project_query.all(), key=lambda project: latest.get(project.id) or project.updated_at, reverse=True
    )[:50]

    return {
        "users": [
            {"id": user.id, "label": user.display_name, "email": user.email} for user in users
        ],
        "projects": [
            {
                "id": project.id,
                "label": project.title,
                "space": space_names.get(project.space_id),
            }
            for project in projects
        ],
    }
