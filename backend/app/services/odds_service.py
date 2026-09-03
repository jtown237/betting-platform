# backend/app/services/odds_service.py
"""Service for fetching and storing odds from OddsAPI."""

import requests
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from sqlalchemy.orm import Session
from app.models import Game, Odds, Sport, Sportsbook, BetType, GameStatus
from app.config import get_settings

logger = logging.getLogger(__name__)

# Mapping of OddsAPI sport keys to our Sport enum
SPORT_MAPPING = {
    "americanfootball_nfl": Sport.NFL,
    "americanfootball_ncaaf": Sport.CFB,
    "baseball_mlb": Sport.MLB
}

# Mapping of OddsAPI sportsbook keys to our Sportsbook enum
SPORTSBOOK_MAPPING = {
    "draftkings": Sportsbook.DRAFTKINGS,
    "fanduel": Sportsbook.FANDUEL,
    "kalshi": Sportsbook.KALSHI
}

# Markets we care about
SUPPORTED_MARKETS = ["h2h", "spreads", "totals"]


def fetch_odds_from_api(sport: str) -> Dict[str, Any]:
    """
    Fetch odds from OddsAPI for a given sport.

    Args:
        sport: Sport key (e.g., "americanfootball_nfl", "baseball_mlb")

    Returns:
        Dict containing games and their odds

    Raises:
        ValueError: If sport is not supported
        Exception: If API call fails
    """
    settings = get_settings()

    if sport not in SPORT_MAPPING:
        raise ValueError(f"Unsupported sport: {sport}")

    api_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": settings.ODDSAPI_KEY,
        "regions": "us",
        "markets": ",".join(SUPPORTED_MARKETS),
        "oddsFormat": "american"
    }

    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch odds from OddsAPI for {sport}: {e}")
        raise


def _parse_moneyline_odds(game_data: Dict[str, Any], bookmaker: Dict[str, Any]) -> List[tuple]:
    """
    Parse moneyline odds from h2h market.

    Returns:
        List of (side, line, odds) tuples where side is the team name
    """
    results = []
    h2h_market = next(
        (m for m in bookmaker.get("markets", []) if m["key"] == "h2h"),
        None
    )

    if h2h_market:
        for outcome in h2h_market.get("outcomes", []):
            team = outcome.get("name")
            price = outcome.get("price")
            if team and price is not None:
                results.append((team, None, price, team))  # (side_for_upsert, line, odds, side_name)

    return results


def _parse_spread_odds(game_data: Dict[str, Any], bookmaker: Dict[str, Any]) -> List[tuple]:
    """
    Parse spread odds from spreads market.

    Returns:
        List of (side, line, odds, side_name) tuples
    """
    results = []
    spreads_market = next(
        (m for m in bookmaker.get("markets", []) if m["key"] == "spreads"),
        None
    )

    if spreads_market:
        for outcome in spreads_market.get("outcomes", []):
            team = outcome.get("name")
            point = outcome.get("point")
            price = outcome.get("price")
            if team and point is not None and price is not None:
                # Store as "{team} {point:+.1f}" format (e.g., "Chiefs -3.0")
                side = f"{team} {point:+.1f}".strip()
                results.append((side, point, price, side))

    return results


def _parse_total_odds(game_data: Dict[str, Any], bookmaker: Dict[str, Any]) -> List[tuple]:
    """
    Parse total (over/under) odds from totals market.

    Returns:
        List of (side, line, odds, side_name) tuples where side is "Over X.X" or "Under X.X"
    """
    results = []
    totals_market = next(
        (m for m in bookmaker.get("markets", []) if m["key"] == "totals"),
        None
    )

    if totals_market:
        for outcome in totals_market.get("outcomes", []):
            outcome_name = outcome.get("name")
            point = outcome.get("point")
            price = outcome.get("price")
            if outcome_name and point is not None and price is not None:
                # outcome_name is "Over" or "Under"
                side = f"{outcome_name} {point:.1f}"
                results.append((side, point, price, side))

    return results


def _extract_games(odds_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Normalise an OddsAPI odds payload to a list of events.

    The live endpoint returns a bare JSON array. Accept the {"games": [...]}
    object form too, which is what the fixtures use.
    """
    if isinstance(odds_data, list):
        return odds_data
    if isinstance(odds_data, dict):
        return odds_data.get("games", [])
    return []


def store_odds(
    db: Session,
    odds_data: Union[Dict[str, Any], List[Dict[str, Any]]],
    sport: str,
) -> int:
    """
    Store odds in the database with upsert logic (latest odds only, no history).

    Args:
        db: Database session
        odds_data: Response from OddsAPI
        sport: Sport key (e.g., "americanfootball_nfl", "baseball_mlb")

    Returns:
        Number of odds records stored/updated

    Raises:
        ValueError: If sport is not supported
    """
    if sport not in SPORT_MAPPING:
        raise ValueError(f"Unsupported sport: {sport}")

    sport_enum = SPORT_MAPPING[sport]
    games = _extract_games(odds_data)
    odds_count = 0

    for game_data in games:
        game_id = game_data.get("id")
        home_team = game_data.get("home_team")
        away_team = game_data.get("away_team")
        commence_time_str = game_data.get("commence_time")

        if not all([game_id, home_team, away_team, commence_time_str]):
            logger.warning(f"Skipping game with missing data: {game_data}")
            continue

        # Parse commence time
        try:
            commence_time = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Failed to parse commence_time for game {game_id}: {e}")
            continue

        # Create or get game
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            game = Game(
                id=game_id,
                sport=sport_enum,
                home_team=home_team,
                away_team=away_team,
                start_time=commence_time,
                status=GameStatus.SCHEDULED
            )
            db.add(game)
            db.flush()
            logger.info(f"Created new game: {game_id}")

        # Process bookmakers
        bookmakers = game_data.get("bookmakers", [])
        for bookmaker in bookmakers:
            bookmaker_key = bookmaker.get("key")
            if bookmaker_key not in SPORTSBOOK_MAPPING:
                continue

            sportsbook = SPORTSBOOK_MAPPING[bookmaker_key]

            # Parse different market types
            odds_list = []

            # Moneyline odds (h2h)
            odds_list.extend([
                (BetType.MONEYLINE, side, line, odds, side_name)
                for side, line, odds, side_name in _parse_moneyline_odds(game_data, bookmaker)
            ])

            # Spread odds
            odds_list.extend([
                (BetType.SPREAD, side, line, odds, side_name)
                for side, line, odds, side_name in _parse_spread_odds(game_data, bookmaker)
            ])

            # Total odds (over/under)
            odds_list.extend([
                (BetType.OVER_UNDER, side, line, odds, side_name)
                for side, line, odds, side_name in _parse_total_odds(game_data, bookmaker)
            ])

            # Store odds (upsert: delete old, insert new)
            # First delete all existing odds for this game/sportsbook
            db.query(Odds).filter(
                Odds.game_id == game_id,
                Odds.sportsbook == sportsbook
            ).delete()

            # Insert new odds records
            for bet_type, side, line, odds_value, side_name in odds_list:
                # Create new odds record
                odds_record = Odds(
                    game_id=game_id,
                    sportsbook=sportsbook,
                    bet_type=bet_type,
                    line=line if line is not None else 0.0,
                    odds=odds_value,
                    side=side_name,
                    game_start_time=commence_time
                )
                db.add(odds_record)
                odds_count += 1

    try:
        db.commit()
        logger.info(f"Stored {odds_count} odds records for {sport}")
    except Exception as e:
        logger.error(f"Failed to store odds for {sport}: {e}")
        db.rollback()
        raise

    return odds_count


def get_odds_by_sport(db: Session, sport: str) -> List[Dict[str, Any]]:
    """
    Get all games with their odds for a given sport.

    Args:
        db: Database session
        sport: Sport value ("NFL", "CFB" or "MLB")

    Returns:
        List of game dicts with embedded odds
    """
    try:
        sport_enum = Sport[sport.upper()]
    except KeyError:
        raise ValueError(f"Invalid sport: {sport}")

    games = db.query(Game).filter(Game.sport == sport_enum).all()

    result = []
    for game in games:
        game_dict = {
            "id": game.id,
            "sport": game.sport.value,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "start_time": game.start_time.isoformat(),
            "status": game.status.value,
            "odds": []
        }

        for odd in game.odds:
            game_dict["odds"].append({
                "sportsbook": odd.sportsbook.value,
                "bet_type": odd.bet_type.value,
                "side": odd.side,
                "line": odd.line,
                "odds": odd.odds,
                "timestamp": odd.timestamp.isoformat() if odd.timestamp else None
            })

        result.append(game_dict)

    return result


def get_odds_by_game_id(db: Session, game_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed odds for a specific game.

    Args:
        db: Database session
        game_id: Game ID

    Returns:
        Game dict with odds, or None if not found
    """
    game = db.query(Game).filter(Game.id == game_id).first()

    if not game:
        return None

    game_dict = {
        "id": game.id,
        "sport": game.sport.value,
        "home_team": game.home_team,
        "away_team": game.away_team,
        "start_time": game.start_time.isoformat(),
        "final_score_home": game.final_score_home,
        "final_score_away": game.final_score_away,
        "status": game.status.value,
        "odds": []
    }

    for odd in game.odds:
        game_dict["odds"].append({
            "sportsbook": odd.sportsbook.value,
            "bet_type": odd.bet_type.value,
            "side": odd.side,
            "line": odd.line,
            "odds": odd.odds,
            "timestamp": odd.timestamp.isoformat() if odd.timestamp else None
        })

    return game_dict
