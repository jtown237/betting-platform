# backend/app/routers/odds.py
"""Router for odds endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.odds_service import get_odds_by_sport, get_odds_by_game_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/odds", tags=["odds"])


@router.get("/{sport}")
def get_odds_for_sport(sport: str, db: Session = Depends(get_db)):
    """
    Get all games with their odds for a given sport.

    Args:
        sport: Sport name ("NFL" or "CFB")
        db: Database session

    Returns:
        List of games with their odds

    Raises:
        HTTPException: If sport is invalid
    """
    try:
        games = get_odds_by_sport(db, sport)
        return {
            "sport": sport,
            "games": games,
            "count": len(games)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get odds for sport {sport}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve odds"
        )


@router.get("/game/{game_id}")
def get_odds_for_game(game_id: str, db: Session = Depends(get_db)):
    """
    Get detailed odds for a specific game.

    Args:
        game_id: Game ID
        db: Database session

    Returns:
        Game with detailed odds

    Raises:
        HTTPException: If game not found
    """
    try:
        game = get_odds_by_game_id(db, game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Game {game_id} not found"
            )
        return game
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get odds for game {game_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve odds"
        )
