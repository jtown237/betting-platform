# backend/tests/test_odds.py
"""Tests for odds service, job, and router."""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from app.models import Base, Game, Odds, Sport, Sportsbook, BetType, GameStatus
from app.database import get_db
from app.services.odds_service import (
    fetch_odds_from_api,
    store_odds,
    get_odds_by_sport,
    get_odds_by_game_id,
    SPORT_MAPPING,
    SPORTSBOOK_MAPPING
)
from app.routers.odds import router as odds_router


# Setup test database
@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test function."""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    yield db
    db.close()

    # Cleanup
    try:
        os.unlink(temp_db.name)
    except:
        pass


@pytest.fixture
def client(test_db):
    """Create a test client with the odds router."""
    app = FastAPI()
    app.include_router(odds_router)

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# Sample OddsAPI response
def get_sample_odds_response():
    """Get a sample OddsAPI response."""
    return {
        "games": [
            {
                "id": "test_game_1",
                "home_team": "Chiefs",
                "away_team": "Bills",
                "commence_time": "2026-09-01T20:00Z",
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Chiefs", "price": -110},
                                    {"name": "Bills", "price": -110}
                                ]
                            },
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Chiefs", "point": -3.0, "price": -110},
                                    {"name": "Bills", "point": 3.0, "price": -110}
                                ]
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "point": 45.5, "price": -110},
                                    {"name": "Under", "point": 45.5, "price": -110}
                                ]
                            }
                        ]
                    },
                    {
                        "key": "fanduel",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Chiefs", "price": -115},
                                    {"name": "Bills", "price": -105}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }


# Tests for fetch_odds_from_api
class TestFetchOddsFromAPI:
    @patch("app.services.odds_service.requests.get")
    def test_fetch_odds_success(self, mock_get):
        """Test successful fetch from OddsAPI."""
        sample_response = get_sample_odds_response()
        mock_get.return_value.json.return_value = sample_response
        mock_get.return_value.raise_for_status.return_value = None

        result = fetch_odds_from_api("americanfootball_nfl")

        assert result == sample_response
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "americanfootball_nfl" in call_args[0][0]
        assert "apiKey" in call_args[1]["params"]

    @patch("app.services.odds_service.requests.get")
    def test_fetch_odds_unsupported_sport(self, mock_get):
        """Test fetch with unsupported sport."""
        with pytest.raises(ValueError, match="Unsupported sport"):
            fetch_odds_from_api("invalid_sport")

    @patch("app.services.odds_service.requests.get")
    def test_fetch_odds_api_error(self, mock_get):
        """Test fetch with API error."""
        mock_get.side_effect = Exception("API error")

        with pytest.raises(Exception):
            fetch_odds_from_api("americanfootball_nfl")

    def test_fetch_cfb_odds(self):
        """Test that CFB (College Football) sport is supported."""
        # Just verify the sport is in the mapping
        assert "americanfootball_ncaaf" in SPORT_MAPPING


# Tests for store_odds
class TestStoreOdds:
    def test_store_odds_creates_game(self, test_db):
        """Test that store_odds creates new games."""
        sample_response = get_sample_odds_response()

        count = store_odds(test_db, sample_response, "americanfootball_nfl")

        # Should have created odds for: h2h (2) + spreads (2) + totals (2) = 6 for DraftKings
        # Plus h2h (2) = 2 for FanDuel
        # Total 8 odds records
        assert count == 8

        # Verify game was created
        game = test_db.query(Game).filter(Game.id == "test_game_1").first()
        assert game is not None
        assert game.home_team == "Chiefs"
        assert game.away_team == "Bills"
        assert game.sport == Sport.NFL

    def test_store_odds_upsert_logic(self, test_db):
        """Test that store_odds replaces old odds (upsert)."""
        # First insert
        sample_response = get_sample_odds_response()
        count1 = store_odds(test_db, sample_response, "americanfootball_nfl")

        # Verify we have 2 moneyline odds records (Chiefs and Bills)
        odds_count_1 = test_db.query(Odds).filter(
            Odds.game_id == "test_game_1",
            Odds.sportsbook == Sportsbook.DRAFTKINGS,
            Odds.bet_type == BetType.MONEYLINE
        ).count()
        assert odds_count_1 == 2

        # Modify response with different odds
        sample_response_2 = get_sample_odds_response()
        sample_response_2["games"][0]["bookmakers"][0]["markets"][0]["outcomes"][0]["price"] = -120

        # Second insert (upsert)
        count2 = store_odds(test_db, sample_response_2, "americanfootball_nfl")

        # Should still have 2 moneyline odds records (same count)
        odds_count_2 = test_db.query(Odds).filter(
            Odds.game_id == "test_game_1",
            Odds.sportsbook == Sportsbook.DRAFTKINGS,
            Odds.bet_type == BetType.MONEYLINE
        ).count()
        assert odds_count_2 == 2

        # Verify the odds were updated for Chiefs
        chiefs_odds = test_db.query(Odds).filter(
            Odds.game_id == "test_game_1",
            Odds.sportsbook == Sportsbook.DRAFTKINGS,
            Odds.bet_type == BetType.MONEYLINE,
            Odds.side == "Chiefs"
        ).first()
        assert chiefs_odds is not None
        assert chiefs_odds.odds == -120

    def test_store_odds_with_spreads(self, test_db):
        """Test that spreads are stored correctly."""
        sample_response = get_sample_odds_response()
        store_odds(test_db, sample_response, "americanfootball_nfl")

        # Verify spread odds
        spread_odds = test_db.query(Odds).filter(
            Odds.game_id == "test_game_1",
            Odds.bet_type == BetType.SPREAD
        ).all()

        assert len(spread_odds) == 2  # 2 spreads (Chiefs and Bills)

        # Verify line values
        lines = sorted([odd.line for odd in spread_odds])
        assert -3.0 in lines
        assert 3.0 in lines

    def test_store_odds_with_totals(self, test_db):
        """Test that totals are stored correctly."""
        sample_response = get_sample_odds_response()
        store_odds(test_db, sample_response, "americanfootball_nfl")

        # Verify total odds
        total_odds = test_db.query(Odds).filter(
            Odds.game_id == "test_game_1",
            Odds.bet_type == BetType.OVER_UNDER
        ).all()

        assert len(total_odds) == 2  # Over and Under

        # Both should have same line (45.5)
        assert all(odd.line == 45.5 for odd in total_odds)

    def test_store_odds_unsupported_sport(self, test_db):
        """Test store_odds with unsupported sport."""
        sample_response = get_sample_odds_response()

        with pytest.raises(ValueError, match="Unsupported sport"):
            store_odds(test_db, sample_response, "invalid_sport")

    def test_store_odds_missing_data(self, test_db):
        """Test store_odds handles missing game data gracefully."""
        response = {
            "games": [
                {
                    "id": "test_game_2",
                    "home_team": "Chiefs",
                    # Missing away_team and commence_time
                    "bookmakers": []
                }
            ]
        }

        count = store_odds(test_db, response, "americanfootball_nfl")
        assert count == 0

        # Verify no game was created
        game = test_db.query(Game).filter(Game.id == "test_game_2").first()
        assert game is None

    def test_store_odds_multiple_sportsbooks(self, test_db):
        """Test storing odds from multiple sportsbooks."""
        sample_response = get_sample_odds_response()
        store_odds(test_db, sample_response, "americanfootball_nfl")

        # Verify we have odds from both DraftKings and FanDuel
        dk_odds = test_db.query(Odds).filter(
            Odds.game_id == "test_game_1",
            Odds.sportsbook == Sportsbook.DRAFTKINGS
        ).count()

        fd_odds = test_db.query(Odds).filter(
            Odds.game_id == "test_game_1",
            Odds.sportsbook == Sportsbook.FANDUEL
        ).count()

        assert dk_odds > 0
        assert fd_odds > 0


# Tests for get_odds_by_sport
class TestGetOddsBySport:
    def test_get_odds_by_sport(self, test_db):
        """Test retrieving odds by sport."""
        sample_response = get_sample_odds_response()
        store_odds(test_db, sample_response, "americanfootball_nfl")

        games = get_odds_by_sport(test_db, "NFL")

        assert len(games) == 1
        assert games[0]["id"] == "test_game_1"
        assert games[0]["home_team"] == "Chiefs"
        assert len(games[0]["odds"]) > 0

    def test_get_odds_by_sport_invalid(self, test_db):
        """Test with invalid sport."""
        with pytest.raises(ValueError, match="Invalid sport"):
            get_odds_by_sport(test_db, "invalid")

    def test_get_odds_by_sport_empty(self, test_db):
        """Test when no games exist for sport."""
        games = get_odds_by_sport(test_db, "NFL")
        assert len(games) == 0

    def test_get_odds_by_sport_cfb(self, test_db):
        """Test retrieving CFB odds."""
        # Create a CFB game manually
        game = Game(
            id="cfb_game_1",
            sport=Sport.CFB,
            home_team="Alabama",
            away_team="Georgia",
            start_time=datetime(2026, 9, 5, 15, 0, tzinfo=timezone.utc),
            status=GameStatus.SCHEDULED
        )
        test_db.add(game)
        test_db.commit()

        games = get_odds_by_sport(test_db, "CFB")

        assert len(games) == 1
        assert games[0]["sport"] == "CFB"


# Tests for get_odds_by_game_id
class TestGetOddsByGameId:
    def test_get_odds_by_game_id(self, test_db):
        """Test retrieving odds for a specific game."""
        sample_response = get_sample_odds_response()
        store_odds(test_db, sample_response, "americanfootball_nfl")

        game = get_odds_by_game_id(test_db, "test_game_1")

        assert game is not None
        assert game["id"] == "test_game_1"
        assert game["home_team"] == "Chiefs"
        assert game["away_team"] == "Bills"
        assert len(game["odds"]) == 8

    def test_get_odds_by_game_id_not_found(self, test_db):
        """Test when game doesn't exist."""
        game = get_odds_by_game_id(test_db, "nonexistent")
        assert game is None


# Tests for API endpoints
class TestOddsRouter:
    def test_get_odds_for_sport_endpoint(self, client, test_db):
        """Test GET /api/odds/{sport} endpoint."""
        sample_response = get_sample_odds_response()
        store_odds(test_db, sample_response, "americanfootball_nfl")

        response = client.get("/api/odds/NFL")

        assert response.status_code == 200
        data = response.json()
        assert data["sport"] == "NFL"
        assert data["count"] == 1
        assert len(data["games"]) == 1
        assert data["games"][0]["home_team"] == "Chiefs"

    def test_get_odds_for_sport_invalid(self, client):
        """Test GET /api/odds/{sport} with invalid sport."""
        response = client.get("/api/odds/invalid")

        assert response.status_code == 400

    def test_get_odds_for_game_endpoint(self, client, test_db):
        """Test GET /api/odds/game/{game_id} endpoint."""
        sample_response = get_sample_odds_response()
        store_odds(test_db, sample_response, "americanfootball_nfl")

        response = client.get("/api/odds/game/test_game_1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_game_1"
        assert data["home_team"] == "Chiefs"
        assert len(data["odds"]) == 8

    def test_get_odds_for_game_not_found(self, client):
        """Test GET /api/odds/game/{game_id} with non-existent game."""
        response = client.get("/api/odds/game/nonexistent")

        assert response.status_code == 404

    def test_odds_endpoint_cfb(self, client, test_db):
        """Test odds endpoint with CFB sport."""
        # Create a CFB game
        game = Game(
            id="cfb_game_1",
            sport=Sport.CFB,
            home_team="Alabama",
            away_team="Georgia",
            start_time=datetime(2026, 9, 5, 15, 0, tzinfo=timezone.utc),
            status=GameStatus.SCHEDULED
        )
        test_db.add(game)
        test_db.commit()

        response = client.get("/api/odds/CFB")

        assert response.status_code == 200
        data = response.json()
        assert data["sport"] == "CFB"
        assert data["count"] == 1
