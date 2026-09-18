"""Pydantic schemas for authentication requests and responses."""

from datetime import datetime
from pydantic import BaseModel, EmailStr


# NOTE: no role field here on purpose. Role is never client-selectable —
# the first account registered on a fresh database becomes the platform
# administrator (see app/auth/router.py), and every promotion after that
# is a direct database update.
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    user_id: str
    role: str
