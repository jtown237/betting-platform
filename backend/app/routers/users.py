# backend/app/routers/users.py
"""Router for user profile and account endpoints."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from jose import JWTError

from app.database import get_db
from app.auth import verify_token
from app.models import User, Bet, BetStatus
from app.schemas import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])


def get_user_id_from_token(authorization: Optional[str] = Header(None)) -> int:
    """
    Extract and verify user_id from JWT token in Authorization header.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        user_id from token

    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

    token = parts[1]

    try:
        user_id = verify_token(token)
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


@router.get("/profile", response_model=UserProfile)
def get_profile(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_token)
):
    """
    Get user profile with account statistics.

    Args:
        db: Database session
        user_id: User ID from JWT token

    Returns:
        UserProfile with bankroll, returns, ROI, and bet statistics

    Raises:
        HTTPException: If user not found
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get all bets for the user
        bets = db.query(Bet).filter(Bet.user_id == user_id).all()

        # Returns and ROI are measured over what was actually staked, not over
        # the whole bankroll: idle cash is not a loss, so a user with no
        # settled bets reports 0.00 rather than their entire starting balance.
        settled = [b for b in bets if b.status != BetStatus.PENDING]
        total_staked = sum(b.amount for b in settled)
        total_payouts = sum(b.payout or 0 for b in settled)
        net_returns = total_payouts - total_staked

        roi_percent = (net_returns / total_staked * 100) if total_staked > 0 else 0.0

        won_count = len([b for b in bets if b.status == BetStatus.WON])
        lost_count = len([b for b in bets if b.status == BetStatus.LOST])
        push_count = len([b for b in bets if b.status == BetStatus.PUSH])

        return UserProfile(
            email=user.email,
            initial_bankroll=user.initial_bankroll,
            total_returns=net_returns,
            total_bets=len(bets),
            bets_won=won_count,
            bets_lost=lost_count,
            bets_push=push_count,
            roi_percent=roi_percent
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve profile for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )
