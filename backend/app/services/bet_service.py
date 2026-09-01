# backend/app/services/bet_service.py
"""Service for managing bets."""

from sqlalchemy.orm import Session
from app.models import Bet, BetStatus, BetType, Sportsbook
from datetime import datetime, timezone


def create_bet(
    db: Session,
    user_id: int,
    game_id: str,
    sportsbook: str,
    bet_type: str,
    amount: float,
    picked_side: str,
    odds_at_placement: float = None
) -> Bet:
    """
    Create a standard bet on a game.

    Args:
        db: Database session
        user_id: ID of the user placing the bet
        game_id: ID of the game
        sportsbook: Sportsbook name (e.g., "DraftKings", "FanDuel")
        bet_type: Type of bet (e.g., "spread", "moneyline")
        amount: Bet amount in dollars
        picked_side: The side picked (e.g., "Chiefs", "Over 45.5")
        odds_at_placement: Optional odds at time of placement

    Returns:
        Bet object
    """
    # Validate sportsbook
    valid_sportsbooks = [s.value for s in Sportsbook]
    if sportsbook not in valid_sportsbooks:
        raise ValueError(f"Invalid sportsbook: {sportsbook}")

    # Validate bet type
    valid_bet_types = [b.value for b in BetType]
    if bet_type not in valid_bet_types:
        raise ValueError(f"Invalid bet type: {bet_type}")

    # Create bet with pending status
    bet = Bet(
        user_id=user_id,
        game_id=game_id,
        sportsbook=Sportsbook(sportsbook),
        bet_type=BetType(bet_type),
        amount=amount,
        picked_side=picked_side,
        odds_at_placement=odds_at_placement,
        status=BetStatus.PENDING,
        created_at=datetime.now(timezone.utc)
    )

    db.add(bet)
    db.commit()
    db.refresh(bet)

    return bet


def create_custom_bet(
    db: Session,
    user_id: int,
    amount: float,
    picked_side: str,
    odds: float,
    notes: str = None
) -> Bet:
    """
    Create a custom bet (not associated with a specific game).

    Args:
        db: Database session
        user_id: ID of the user placing the bet
        amount: Bet amount in dollars
        picked_side: Description of what was picked
        odds: Odds for the bet
        notes: Optional notes about the bet

    Returns:
        Bet object
    """
    # Create custom bet with no game_id
    bet = Bet(
        user_id=user_id,
        game_id=None,
        sportsbook=Sportsbook.CUSTOM,
        bet_type=BetType.CUSTOM,
        amount=amount,
        picked_side=picked_side,
        odds_at_placement=odds,
        status=BetStatus.PENDING,
        notes=notes,
        created_at=datetime.now(timezone.utc)
    )

    db.add(bet)
    db.commit()
    db.refresh(bet)

    return bet


def settle_custom_bet(
    db: Session,
    user_id: int,
    bet_id: int,
    status: str,
    payout: float = None
) -> Bet:
    """
    Manually settle a custom bet.

    Args:
        db: Database session
        user_id: ID of the user (for authorization)
        bet_id: ID of the bet to settle
        status: Final status ("won", "lost", or "push")
        payout: Amount won/lost

    Returns:
        Updated Bet object

    Raises:
        ValueError: If bet not found or doesn't belong to user
        ValueError: If invalid status
    """
    # Validate status
    valid_statuses = ["won", "lost", "push"]
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

    # Get bet
    bet = db.query(Bet).filter(Bet.id == bet_id, Bet.user_id == user_id).first()
    if not bet:
        raise ValueError(f"Bet {bet_id} not found or does not belong to user")

    # Update bet status
    bet.status = BetStatus(status)
    bet.payout = payout
    bet.settled_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(bet)

    return bet
