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
    name: str


class SpaceResponse(BaseModel):
    id: str
    user_id: str
    name: str

    class Config:
        from_attributes = True


@router.post("", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
def create_space(
    space_in: SpaceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SpaceResponse:
    """Create a new Space for the authenticated user."""
    space_id = str(uuid.uuid4())
    space = crud.create_space(db, space_id=space_id, user_id=current_user.id, name=space_in.name)
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
