# backend/app/services/scoring_service.py
import requests
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.config import get_settings
from app.models import Game, Bet, BetStatus, BetType, GameStatus, Sport
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

# ESPN groups its scoreboards by league path. Keys are the lowercased
# Sport enum values, since callers pass game.sport.value.lower().
ESPN_SPORT_PATHS = {
    "nfl": "sports/football/nfl",
    "cfb": "sports/football/college-football",
    "mlb": "sports/baseball/mlb",
}

def fetch_game_score(game_id: str, sport: str = "nfl") -> dict:
    """
    Fetch game score from ESPN API.

    Args:
        game_id: The ESPN game ID
        sport: Sport type - "nfl", "cfb" (college football) or "mlb"

    Returns a dict with: {home_score, away_score, status}
    """
    # Route to correct ESPN API endpoint based on sport
    sport_path = ESPN_SPORT_PATHS.get(sport.lower(), ESPN_SPORT_PATHS["nfl"])

    url = f"{settings.ESPN_API_BASE}/{sport_path}/games/{game_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract relevant data from ESPN response
        competition = data.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])

        home_score = None
        away_score = None
        status = "unknown"

        for competitor in competitors:
            if competitor.get("homeAway") == "home":
                home_score = competitor.get("score")
            elif competitor.get("homeAway") == "away":
                away_score = competitor.get("score")

        # Map ESPN status to our GameStatus
        espn_status = data.get("status", {}).get("type", "").lower()
        if "final" in espn_status or "completed" in espn_status:
            status = GameStatus.COMPLETED.value
        elif "live" in espn_status or "in progress" in espn_status or "inprogress" in espn_status:
            status = GameStatus.LIVE.value

        return {
            "home_score": home_score,
            "away_score": away_score,
            "status": status
        }
    except requests.RequestException as e:
        logger.error(f"Error fetching score for game {game_id}: {e}")
        raise

def calculate_payout(amount: float, odds: float, won: bool) -> float:
    """
    Calculate payout based on American odds.
    odds: positive or negative American odds (e.g., -110, +200)
    """
    if not won:
        return 0.0

    if odds < 0:
        # Negative odds: e.g., -110 means you need to bet $110 to win $100
        payout = amount * (100 / abs(odds))
    else:
        # Positive odds: e.g., +200 means $100 bet wins $200
        payout = amount * (odds / 100)

    # Total payout includes original stake
    return amount + payout

def settle_spread_bet(
    bet: Bet,
    home_score: int,
    away_score: int,
    picked_side: str,
    odds: float
) -> tuple:
    """
    Settle a spread bet.
    picked_side format: "Team +/-X.X" or just "+/-X.X"
    Returns (status, payout)
    """
    # Parse the spread line from picked_side
    try:
        # Remove team name if present, extract just the line
        if any(char.isdigit() or char in ['+', '-', '.'] for char in picked_side[-10:]):
            line_str = None
            parts = picked_side.split()
            for part in reversed(parts):
                if part[0] in ['+', '-']:
                    line_str = part
                    break
            if not line_str:
                logger.error(f"Cannot parse spread from {picked_side}")
                return BetStatus.PENDING, None
            line = float(line_str)
        else:
            return BetStatus.PENDING, None

        # Determine if bet was on home or away
        home_favored = line < 0
        away_spread = line  # spread applied to away team

        # Calculate spread score
        adjusted_home_score = home_score + away_spread

        # Determine winner
        if adjusted_home_score > away_score:
            won = (line < 0)  # Home was favored (spread is negative)
        elif adjusted_home_score < away_score:
            won = (line > 0)  # Away was favored (spread is positive)
        else:
            # Push
            return BetStatus.PUSH, float(bet.amount)

        if won:
            payout = calculate_payout(bet.amount, odds, True)
            return BetStatus.WON, payout
        else:
            return BetStatus.LOST, 0.0

    except Exception as e:
        logger.error(f"Error settling spread bet {bet.id}: {e}")
        return BetStatus.PENDING, None

def settle_moneyline_bet(
    bet: Bet,
    home_score: int,
    away_score: int,
    picked_side: str,
    odds: float,
    game: Game = None
) -> tuple:
    """
    Settle a moneyline bet.
    picked_side: team name or identifier (e.g., "Chiefs", "Bills", or legacy "home"/"away")
    game: Game object for team name matching (enables proper settlement with real team names)
    Returns (status, payout)
    """
    try:
        if home_score == away_score:
            # Push (tie)
            return BetStatus.PUSH, float(bet.amount)

        home_wins = home_score > away_score

        # Determine if user picked the home team
        picked_home = False

        if game:
            # Try to match against actual team names first
            # Check if picked_side matches home team or away team names
            home_match = (
                picked_side.lower() in game.home_team.lower() or
                game.home_team.lower() in picked_side.lower()
            )
            away_match = (
                picked_side.lower() in game.away_team.lower() or
                game.away_team.lower() in picked_side.lower()
            )

            if home_match:
                picked_home = True
            elif away_match:
                picked_home = False
            else:
                # Fallback to legacy format if no team name match
                picked_home = "home" in picked_side.lower() or picked_side.lower() in ["h", "home"]
        else:
            # Fallback for legacy support (when no game object provided)
            picked_home = "home" in picked_side.lower() or picked_side.lower() in ["h", "home"]

        won = (picked_home and home_wins) or (not picked_home and not home_wins)

        if won:
            payout = calculate_payout(bet.amount, odds, True)
            return BetStatus.WON, payout
        else:
            return BetStatus.LOST, 0.0

    except Exception as e:
        logger.error(f"Error settling moneyline bet {bet.id}: {e}")
        return BetStatus.PENDING, None

def settle_over_under_bet(
    bet: Bet,
    home_score: int,
    away_score: int,
    picked_side: str,
    odds: float
) -> tuple:
    """
    Settle an over/under bet.
    picked_side: "Over X.X" or "Under X.X"
    Returns (status, payout)
    """
    try:
        # Parse total from picked_side
        total_str = None
        parts = picked_side.split()
        for i, part in enumerate(parts):
            if part.lower() in ["over", "under"]:
                if i + 1 < len(parts):
                    try:
                        total_str = float(parts[i + 1])
                    except ValueError:
                        pass

        if total_str is None:
            logger.error(f"Cannot parse total from {picked_side}")
            return BetStatus.PENDING, None

        total_score = home_score + away_score
        is_over_pick = "over" in picked_side.lower()

        if total_score == total_str:
            # Push
            return BetStatus.PUSH, float(bet.amount)

        won = (total_score > total_str and is_over_pick) or (total_score < total_str and not is_over_pick)

        if won:
            payout = calculate_payout(bet.amount, odds, True)
            return BetStatus.WON, payout
        else:
            return BetStatus.LOST, 0.0

    except Exception as e:
        logger.error(f"Error settling over/under bet {bet.id}: {e}")
        return BetStatus.PENDING, None

def settle_bets_for_game(
    db: Session,
    game_id: str,
    final_home_score: int,
    final_away_score: int
) -> dict:
    """
    Settle all pending bets for a completed game.
    Returns dict with counts of settled bets by status.
    """
    result = {"won": 0, "lost": 0, "push": 0, "error": 0}

    # Get all pending bets for this game
    pending_bets = db.query(Bet).filter(
        and_(
            Bet.game_id == game_id,
            Bet.status == BetStatus.PENDING
        )
    ).all()

    if not pending_bets:
        logger.info(f"No pending bets found for game {game_id}")
        return result

    # Get the game to find home/away teams
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        logger.error(f"Game {game_id} not found")
        return result

    for bet in pending_bets:
        try:
            status = BetStatus.PENDING
            payout = None

            odds = bet.odds_locked_at or -110  # Default to -110 if not set

            if bet.bet_type == BetType.SPREAD:
                status, payout = settle_spread_bet(
                    bet, final_home_score, final_away_score,
                    bet.picked_side, odds
                )
            elif bet.bet_type == BetType.MONEYLINE:
                status, payout = settle_moneyline_bet(
                    bet, final_home_score, final_away_score,
                    bet.picked_side, odds, game
                )
            elif bet.bet_type == BetType.OVER_UNDER:
                status, payout = settle_over_under_bet(
                    bet, final_home_score, final_away_score,
                    bet.picked_side, odds
                )
            elif bet.bet_type == BetType.CUSTOM:
                # Custom bets are not auto-settled, skip
                continue
            else:
                logger.warning(f"Unknown bet type for bet {bet.id}: {bet.bet_type}")
                result["error"] += 1
                continue

            if status == BetStatus.PENDING:
                # Settlement logic failed
                result["error"] += 1
                continue

            # Update bet
            bet.status = status
            bet.payout = payout
            bet.settled_at = utc_now()

            result[status.value] += 1
            logger.info(f"Settled bet {bet.id}: {status.value}")

        except Exception as e:
            logger.error(f"Error settling bet {bet.id}: {e}")
            result["error"] += 1

    db.commit()
    logger.info(f"Game {game_id} settlement complete: {result}")
    return result

def poll_and_settle_scores(db: Session) -> dict:
    """
    Poll all active games for scores and settle completed ones.
    Returns summary of games processed.
    """
    summary = {
        "games_checked": 0,
        "games_settled": 0,
        "total_bets_settled": 0,
        "errors": 0
    }

    # Get all non-completed games
    active_games = db.query(Game).filter(
        Game.status != GameStatus.COMPLETED
    ).all()

    logger.info(f"Checking {len(active_games)} active games")

    for game in active_games:
        try:
            summary["games_checked"] += 1
            score_data = fetch_game_score(game.id, sport=game.sport.value.lower())

            if score_data["status"] == GameStatus.COMPLETED.value:
                # Update game status and scores
                game.final_score_home = score_data["home_score"]
                game.final_score_away = score_data["away_score"]
                game.status = GameStatus.COMPLETED
                db.commit()

                # Settle bets for this game
                settlement = settle_bets_for_game(
                    db,
                    game.id,
                    score_data["home_score"],
                    score_data["away_score"]
                )

                summary["games_settled"] += 1
                total_settled = settlement["won"] + settlement["lost"] + settlement["push"]
                summary["total_bets_settled"] += total_settled

                if settlement["error"] > 0:
                    summary["errors"] += settlement["error"]

        except Exception as e:
            logger.error(f"Error processing game {game.id}: {e}")
            summary["errors"] += 1

    logger.info(f"Scoring poll complete: {summary}")
    return summary
