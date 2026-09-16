"""FastAPI router for user authentication endpoints."""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas import Token, UserCreate, UserLogin, UserResponse
from app.auth.service import create_access_token, hash_password, verify_password
from app.db import crud
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Annotated[Session, Depends(get_db)]) -> Token:
    """Register a new user and return JWT token."""
    existing = crud.get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
    user_id = str(uuid.uuid4())
    hashed_pwd = hash_password(user_in.password)
    user = crud.create_user(
        db,
        user_id=user_id,
        email=user_in.email,
        hashed_password=hashed_pwd,
        display_name=user_in.display_name,
        role=user_in.role,
    )
    access_token = create_access_token(user_id=user.id, role=user.role)
    return Token(access_token=access_token, token_type="bearer", user=UserResponse.model_validate(user))


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Annotated[Session, Depends(get_db)]) -> Token:
    """Authenticate email/password and return JWT token."""
    user = crud.get_user_by_email(db, credentials.email)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(user_id=user.id, role=user.role)
    return Token(access_token=access_token, token_type="bearer", user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """Return currently authenticated user info."""
    return UserResponse.model_validate(current_user)
