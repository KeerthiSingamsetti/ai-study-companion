"""FastAPI router for user Spaces (project containers)."""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import crud
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/spaces", tags=["spaces"])


class SpaceCreate(BaseModel):
    """A Space requires a name and description, with optional visual customization."""

    name: str
    description: str | None = None
    accent: str | None = None
    icon: str | None = None


class SpaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    accent: str | None = None
    icon: str | None = None


class SpaceResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    accent: str | None = None
    icon: str | None = None

    class Config:
        from_attributes = True


@router.post("", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
def create_space(
    space_in: SpaceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SpaceResponse:
    """Create a new Space for the authenticated user."""
    name = " ".join(space_in.name.split())
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Space name cannot be blank.")
    space_id = str(uuid.uuid4())
    space = crud.create_space(
        db,
        space_id=space_id,
        user_id=current_user.id,
        name=name,
        description=" ".join((space_in.description or "").split()) or None,
        accent=space_in.accent,
        icon=space_in.icon,
    )
    return SpaceResponse.model_validate(space)


@router.patch("/{space_id}", response_model=SpaceResponse)
def update_space(
    space_id: str,
    payload: SpaceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SpaceResponse:
    """Update a Space's name, description or visual customization."""
    if crud.get_space(db, space_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found.")
    if payload.name is None and payload.description is None and payload.accent is None and payload.icon is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nothing to update.")
    space = crud.update_space(
        db,
        space_id=space_id,
        user_id=current_user.id,
        name=" ".join(payload.name.split()) if payload.name is not None else None,
        description=" ".join(payload.description.split()) if payload.description is not None else None,
        accent=payload.accent,
        icon=payload.icon,
    )
    return SpaceResponse.model_validate(space)


@router.get("", response_model=list[SpaceResponse])
def list_spaces(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SpaceResponse]:
    """List all spaces owned by current user."""
    spaces = crud.list_spaces_for_user(db, current_user.id)
    return [SpaceResponse.model_validate(s) for s in spaces]


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space(
    space_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a space owned by current user."""
    deleted = crud.delete_space(db, space_id=space_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found.")
