# backend/app/routers/bets.py
"""Router for bet placement and management endpoints."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from jose import JWTError

from app.database import get_db
from app.auth import verify_token
from app.models import Bet, BetStatus
from app.schemas import BetCreate, BetCreateCustom, BetResponse, BetSettle
from app.services.bet_service import create_bet, create_custom_bet, settle_custom_bet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bets", tags=["bets"])


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


@router.post("", response_model=BetResponse)
def place_bet(
    bet_request: BetCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_token)
):
    """
    Place a bet on a game.

    Args:
        bet_request: BetCreate with game_id, sportsbook, bet_type, amount, picked_side
        db: Database session
        user_id: User ID from JWT token

    Returns:
        BetResponse with bet_id and status

    Raises:
        HTTPException: If validation fails
    """
    try:
        bet = create_bet(
            db=db,
            user_id=user_id,
            game_id=bet_request.game_id,
            sportsbook=bet_request.sportsbook,
            bet_type=bet_request.bet_type,
            amount=bet_request.amount,
            picked_side=bet_request.picked_side
        )
        return BetResponse(
            bet_id=bet.id,
            status=bet.status.value,
            amount=bet.amount,
            picked_side=bet.picked_side,
            odds_locked_at=bet.odds_locked_at,
            created_at=bet.created_at.isoformat() if bet.created_at else None,
            game_id=bet.game_id,
            sportsbook=bet.sportsbook.value,
            bet_type=bet.bet_type.value
        )
    except ValueError as e:
        logger.warning(f"Invalid bet parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create bet for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to place bet"
        )


@router.post("/custom", response_model=BetResponse)
def place_custom_bet(
    bet_request: BetCreateCustom,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_token)
):
    """
    Place a custom bet (not associated with a specific game).

    Args:
        bet_request: BetCreateCustom with amount, picked_side, odds, notes
        db: Database session
        user_id: User ID from JWT token

    Returns:
        BetResponse with bet_id and status

    Raises:
        HTTPException: If validation fails
    """
    try:
        bet = create_custom_bet(
            db=db,
            user_id=user_id,
            amount=bet_request.amount,
            picked_side=bet_request.picked_side,
            odds=bet_request.odds,
            notes=bet_request.notes
        )
        return BetResponse(
            bet_id=bet.id,
            status=bet.status.value,
            amount=bet.amount,
            picked_side=bet.picked_side,
            odds_locked_at=bet.odds_locked_at,
            created_at=bet.created_at.isoformat() if bet.created_at else None,
            notes=bet.notes,
            sportsbook=bet.sportsbook.value,
            bet_type=bet.bet_type.value
        )
    except ValueError as e:
        logger.warning(f"Invalid custom bet parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create custom bet for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to place custom bet"
        )


@router.get("/active", response_model=list[BetResponse])
def get_active_bets(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_token)
):
    """
    Get all active (pending) bets for the user.

    Args:
        db: Database session
        user_id: User ID from JWT token

    Returns:
        List of pending BetResponse objects
    """
    try:
        bets = db.query(Bet).filter(
            Bet.user_id == user_id,
            Bet.status == BetStatus.PENDING
        ).all()

        return [
            BetResponse(
                bet_id=bet.id,
                status=bet.status.value,
                amount=bet.amount,
                picked_side=bet.picked_side,
                odds_locked_at=bet.odds_locked_at,
                payout=bet.payout,
                created_at=bet.created_at.isoformat() if bet.created_at else None,
                settled_at=bet.settled_at.isoformat() if bet.settled_at else None,
                notes=bet.notes,
                game_id=bet.game_id,
                sportsbook=bet.sportsbook.value if bet.sportsbook else None,
                bet_type=bet.bet_type.value if bet.bet_type else None
            )
            for bet in bets
        ]
    except Exception as e:
        logger.error(f"Failed to retrieve active bets for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active bets"
        )


@router.get("/history", response_model=list[BetResponse])
def get_bet_history(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_token)
):
    """
    Get all settled bets for the user.

    Args:
        db: Database session
        user_id: User ID from JWT token

    Returns:
        List of settled BetResponse objects
    """
    try:
        bets = db.query(Bet).filter(
            Bet.user_id == user_id,
            Bet.status.in_([BetStatus.WON, BetStatus.LOST, BetStatus.PUSH])
        ).all()

        return [
            BetResponse(
                bet_id=bet.id,
                status=bet.status.value,
                amount=bet.amount,
                picked_side=bet.picked_side,
                odds_locked_at=bet.odds_locked_at,
                payout=bet.payout,
                created_at=bet.created_at.isoformat() if bet.created_at else None,
                settled_at=bet.settled_at.isoformat() if bet.settled_at else None,
                notes=bet.notes,
                game_id=bet.game_id,
                sportsbook=bet.sportsbook.value if bet.sportsbook else None,
                bet_type=bet.bet_type.value if bet.bet_type else None
            )
            for bet in bets
        ]
    except Exception as e:
        logger.error(f"Failed to retrieve bet history for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bet history"
        )


@router.get("/{bet_id}", response_model=BetResponse)
def get_bet(
    bet_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_token)
):
    """
    Get details for a specific bet.

    Args:
        bet_id: ID of the bet
        db: Database session
        user_id: User ID from JWT token

    Returns:
        BetResponse with bet details

    Raises:
        HTTPException: If bet not found or doesn't belong to user
    """
    try:
        bet = db.query(Bet).filter(
            Bet.id == bet_id,
            Bet.user_id == user_id
        ).first()

        if not bet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bet {bet_id} not found"
            )

        return BetResponse(
            bet_id=bet.id,
            status=bet.status.value,
            amount=bet.amount,
            picked_side=bet.picked_side,
            odds_locked_at=bet.odds_locked_at,
            payout=bet.payout,
            created_at=bet.created_at.isoformat() if bet.created_at else None,
            settled_at=bet.settled_at.isoformat() if bet.settled_at else None,
            notes=bet.notes,
            game_id=bet.game_id,
            sportsbook=bet.sportsbook.value if bet.sportsbook else None,
            bet_type=bet.bet_type.value if bet.bet_type else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve bet {bet_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bet"
        )


@router.patch("/{bet_id}/settle", response_model=BetResponse)
def settle_bet(
    bet_id: int,
    settle_request: BetSettle,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id_from_token)
):
    """
    Manually settle a custom bet.

    Args:
        bet_id: ID of the bet to settle
        settle_request: BetSettle with status and optional payout
        db: Database session
        user_id: User ID from JWT token

    Returns:
        BetResponse with updated bet

    Raises:
        HTTPException: If bet not found, invalid status, or authorization fails
    """
    try:
        bet = settle_custom_bet(
            db=db,
            user_id=user_id,
            bet_id=bet_id,
            status=settle_request.status,
            payout=settle_request.payout
        )

        return BetResponse(
            bet_id=bet.id,
            status=bet.status.value,
            amount=bet.amount,
            picked_side=bet.picked_side,
            odds_locked_at=bet.odds_locked_at,
            payout=bet.payout,
            created_at=bet.created_at.isoformat() if bet.created_at else None,
            settled_at=bet.settled_at.isoformat() if bet.settled_at else None,
            notes=bet.notes,
            sportsbook=bet.sportsbook.value if bet.sportsbook else None,
            bet_type=bet.bet_type.value if bet.bet_type else None
        )
    except ValueError as e:
        logger.warning(f"Failed to settle bet {bet_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to settle bet {bet_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to settle bet"
        )
