# backend/app/schemas.py
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    initial_bankroll: float = Field(..., gt=0)


class LoginRequest(BaseModel):
    """Request schema for user login."""
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Response schema for authentication endpoints."""
    user_id: int
    token: str
