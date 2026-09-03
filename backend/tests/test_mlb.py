# backend/tests/test_mlb.py
"""Tests for MLB support, and regressions for the payload shape and id width.

The odds path had three defects that all produced an empty board and that
SQLite hid from the rest of the suite:

  * OddsAPI returns a bare JSON array, but store_odds read
    odds_data["games"], so every poll raised AttributeError.
  * Event ids are 32-character hex, but the id columns were String(20).
    SQLite ignores VARCHAR limits entirely -- it stores the full string
    without error -- so no round-trip test can catch this. Only the
    declared column width can be asserted portably.

The fixtures here therefore mirror the live response exactly.
"""

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.jobs.odds_job import SPORTS_TO_POLL
from app.models import Base, Bet, Game, Odds, Sport
from app.routers.odds import router as odds_router
from app.services.odds_service import SPORT_MAPPING, get_odds_by_sport, store_odds
from app.services.scoring_service import ESPN_SPORT_PATHS

# A real OddsAPI event id: 32 hex characters.
MLB_EVENT_ID = "e912304de2b2ce35b473ce2ecd3d1502"


@pytest.fixture(scope="function")
def test_db():
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    engine = create_engine(
        f"sqlite:///{temp_db.name}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield db
    db.close()
    try:
        os.unlink(temp_db.name)
    except OSError:
        pass


@pytest.fixture
def client(test_db):
    app = FastAPI()
    app.include_router(odds_router)
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def live_shape_mlb_response():
    """A bare array, exactly as /v4/sports/baseball_mlb/odds returns it."""
    return [
        {
            "id": MLB_EVENT_ID,
            "sport_key": "baseball_mlb",
            "commence_time": "2026-09-03T23:10:00Z",
            "home_team": "Los Angeles Dodgers",
            "away_team": "San Francisco Giants",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Los Angeles Dodgers", "price": -150},
                                {"name": "San Francisco Giants", "price": 130},
                            ],
                        },
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": "Los Angeles Dodgers", "point": -1.5, "price": 115},
                                {"name": "San Francisco Giants", "point": 1.5, "price": -135},
                            ],
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "point": 8.5, "price": -105},
                                {"name": "Under", "point": 8.5, "price": -115},
                            ],
                        },
                    ],
                }
            ],
        }
    ]


class TestMlbWiring:
    def test_mlb_is_mapped_to_the_sport_enum(self):
        assert SPORT_MAPPING["baseball_mlb"] is Sport.MLB

    def test_mlb_is_polled(self):
        assert "baseball_mlb" in SPORTS_TO_POLL

    def test_mlb_has_an_espn_path(self):
        # scoring passes game.sport.value.lower()
        assert ESPN_SPORT_PATHS[Sport.MLB.value.lower()] == "sports/baseball/mlb"

    def test_every_sport_has_an_espn_path(self):
        missing = [s.value for s in Sport if s.value.lower() not in ESPN_SPORT_PATHS]
        assert missing == [], f"sports with no ESPN path: {missing}"


class TestLiveResponseShape:
    def test_store_odds_accepts_a_bare_array(self, test_db):
        """The live endpoint returns a list, not {"games": [...]}."""
        count = store_odds(test_db, live_shape_mlb_response(), "baseball_mlb")
        assert count > 0

        game = test_db.query(Game).filter(Game.id == MLB_EVENT_ID).first()
        assert game is not None
        assert game.sport is Sport.MLB
        assert game.home_team == "Los Angeles Dodgers"

    def test_thirty_two_character_event_id_survives_a_round_trip(self, test_db):
        """Guards the id plumbing. Width itself is asserted on the model,
        since SQLite would pass this even with String(20)."""
        store_odds(test_db, live_shape_mlb_response(), "baseball_mlb")

        game = test_db.query(Game).filter(Game.id == MLB_EVENT_ID).first()
        assert game is not None
        assert game.id == MLB_EVENT_ID
        assert len(game.id) == 32

        # The odds rows must point back at the untruncated id.
        odds = test_db.query(Odds).filter(Odds.game_id == MLB_EVENT_ID).all()
        assert odds, "no odds linked to the full-length game id"

    def test_run_line_and_total_are_stored(self, test_db):
        store_odds(test_db, live_shape_mlb_response(), "baseball_mlb")
        lines = {o.line for o in test_db.query(Odds).all()}
        assert -1.5 in lines, "run line missing"
        assert 8.5 in lines, "total missing"


class TestIdColumnWidth:
    """SQLite never enforces VARCHAR length, so assert the declaration."""

    @pytest.mark.parametrize(
        "column",
        [
            Game.__table__.c.id,
            Bet.__table__.c.game_id,
            Odds.__table__.c.game_id,
        ],
        ids=["games.id", "bets.game_id", "odds.game_id"],
    )
    def test_holds_a_32_character_event_id(self, column):
        assert column.type.length >= 32, (
            f"{column} is String({column.type.length}); OddsAPI event ids are "
            "32 characters and Postgres rejects anything longer than the column"
        )


class TestMlbEndpoint:
    def test_odds_endpoint_serves_mlb(self, client, test_db):
        store_odds(test_db, live_shape_mlb_response(), "baseball_mlb")
        test_db.commit()

        response = client.get("/api/odds/MLB")
        assert response.status_code == 200
        body = response.json()
        assert body["sport"] == "MLB"
        assert body["count"] >= 1
        assert body["games"][0]["home_team"] == "Los Angeles Dodgers"

    def test_mlb_odds_are_not_returned_for_nfl(self, client, test_db):
        store_odds(test_db, live_shape_mlb_response(), "baseball_mlb")
        test_db.commit()

        assert client.get("/api/odds/NFL").json()["count"] == 0

    def test_odds_identify_which_team_they_belong_to(self, client, test_db):
        """store_odds records `side`, but both serializers omitted it, so a
        moneyline pair reached the dashboard as two numbers with no team."""
        store_odds(test_db, live_shape_mlb_response(), "baseball_mlb")
        test_db.commit()

        odds = client.get("/api/odds/MLB").json()["games"][0]["odds"]

        moneylines = [o for o in odds if o["bet_type"] == "moneyline"]
        assert {o["side"] for o in moneylines} == {
            "Los Angeles Dodgers",
            "San Francisco Giants",
        }

        spreads = [o for o in odds if o["bet_type"] == "spread"]
        assert all(o["side"] for o in spreads), "run lines have no team"

        totals = [o for o in odds if o["bet_type"] == "over_under"]
        assert {o["side"] for o in totals} == {"Over 8.5", "Under 8.5"}

    def test_get_odds_by_sport_filters_to_mlb(self, test_db):
        store_odds(test_db, live_shape_mlb_response(), "baseball_mlb")
        assert len(get_odds_by_sport(test_db, "MLB")) >= 1
        assert get_odds_by_sport(test_db, "CFB") == []
