# backend/app/schemas.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


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


class BetCreate(BaseModel):
    """Request schema for creating a standard bet."""
    game_id: str
    sportsbook: str
    bet_type: str
    amount: float = Field(..., gt=0)
    picked_side: str


class BetCreateCustom(BaseModel):
    """Request schema for creating a custom bet."""
    amount: float = Field(..., gt=0)
    picked_side: str
    odds: float
    notes: Optional[str] = None


class BetSettle(BaseModel):
    """Request schema for settling a bet."""
    status: str
    payout: Optional[float] = None


class BetResponse(BaseModel):
    """Response schema for bet endpoints."""
    bet_id: int
    status: str
    amount: Optional[float] = None
    picked_side: Optional[str] = None
    odds_locked_at: Optional[float] = None
    payout: Optional[float] = None
    created_at: Optional[str] = None
    settled_at: Optional[str] = None
    notes: Optional[str] = None
    game_id: Optional[str] = None
    sportsbook: Optional[str] = None
    bet_type: Optional[str] = None


class UserProfile(BaseModel):
    """Response schema for user profile endpoint."""
    email: str
    initial_bankroll: float
    total_returns: float
    total_bets: int
    bets_won: int
    bets_lost: int
    bets_push: int
    roi_percent: float
