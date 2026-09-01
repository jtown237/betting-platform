# backend/tests/test_bets.py
"""Tests for bet placement and management endpoints."""

import pytest
import tempfile
import os
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Game, Sport, GameStatus, Bet, BetStatus, Sportsbook, BetType
from app.database import get_db
from app.routers.bets import router as bets_router
from app.routers.auth import router as auth_router
from app.auth import create_access_token
from app.services.bet_service import create_bet, create_custom_bet, settle_custom_bet


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
    """Create a test client with both auth and bets routers."""
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(bets_router)

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
        initial_bankroll=10000.0
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_game(test_db):
    """Create a test game."""
    game = Game(
        id="test_game_1",
        sport=Sport.NFL,
        home_team="Chiefs",
        away_team="Bills",
        start_time=datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc),
        status=GameStatus.SCHEDULED
    )
    test_db.add(game)
    test_db.commit()
    test_db.refresh(game)
    return game


@pytest.fixture
def auth_headers(test_user):
    """Generate valid auth headers for test user."""
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


class TestCreateBetService:
    """Tests for create_bet service function."""

    def test_create_bet_success(self, test_db, test_user, test_game):
        """Test creating a standard bet."""
        bet = create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        assert bet.id is not None
        assert bet.user_id == test_user.id
        assert bet.game_id == test_game.id
        assert bet.sportsbook == Sportsbook.DRAFTKINGS
        assert bet.bet_type == BetType.SPREAD
        assert bet.amount == 100.0
        assert bet.picked_side == "Chiefs"
        assert bet.status == BetStatus.PENDING

    def test_create_bet_invalid_sportsbook(self, test_db, test_user, test_game):
        """Test creating bet with invalid sportsbook."""
        with pytest.raises(ValueError, match="Invalid sportsbook"):
            create_bet(
                db=test_db,
                user_id=test_user.id,
                game_id=test_game.id,
                sportsbook="InvalidBook",
                bet_type="spread",
                amount=100.0,
                picked_side="Chiefs"
            )

    def test_create_bet_invalid_bet_type(self, test_db, test_user, test_game):
        """Test creating bet with invalid bet type."""
        with pytest.raises(ValueError, match="Invalid bet type"):
            create_bet(
                db=test_db,
                user_id=test_user.id,
                game_id=test_game.id,
                sportsbook="DraftKings",
                bet_type="invalid_type",
                amount=100.0,
                picked_side="Chiefs"
            )

    def test_create_bet_with_odds(self, test_db, test_user, test_game):
        """Test creating bet with odds at placement."""
        bet = create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="FanDuel",
            bet_type="moneyline",
            amount=50.0,
            picked_side="Bills",
            odds_at_placement=-110.0
        )

        assert bet.odds_locked_at == -110.0

    def test_create_bet_game_not_found(self, test_db, test_user):
        """Test creating bet on non-existent game."""
        with pytest.raises(ValueError, match="not found"):
            create_bet(
                db=test_db,
                user_id=test_user.id,
                game_id="nonexistent_game",
                sportsbook="DraftKings",
                bet_type="spread",
                amount=100.0,
                picked_side="Chiefs"
            )


class TestCreateCustomBetService:
    """Tests for create_custom_bet service function."""

    def test_create_custom_bet_success(self, test_db, test_user):
        """Test creating a custom bet."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=75.0,
            picked_side="Team A to score first",
            odds=+200.0,
            notes="Custom prop bet"
        )

        assert bet.id is not None
        assert bet.user_id == test_user.id
        assert bet.game_id is None
        assert bet.sportsbook == Sportsbook.CUSTOM
        assert bet.bet_type == BetType.CUSTOM
        assert bet.amount == 75.0
        assert bet.picked_side == "Team A to score first"
        assert bet.odds_locked_at == +200.0
        assert bet.notes == "Custom prop bet"
        assert bet.status == BetStatus.PENDING

    def test_create_custom_bet_without_notes(self, test_db, test_user):
        """Test creating custom bet without notes."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=50.0,
            picked_side="Player X over 100 yards",
            odds=-110.0
        )

        assert bet.notes is None
        assert bet.picked_side == "Player X over 100 yards"


class TestSettleCustomBetService:
    """Tests for settle_custom_bet service function."""

    def test_settle_custom_bet_won(self, test_db, test_user):
        """Test settling a custom bet as won."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test pick",
            odds=+100.0
        )

        settled_bet = settle_custom_bet(
            db=test_db,
            user_id=test_user.id,
            bet_id=bet.id,
            status="won",
            payout=200.0
        )

        assert settled_bet.status == BetStatus.WON
        assert settled_bet.payout == 200.0
        assert settled_bet.settled_at is not None

    def test_settle_custom_bet_lost(self, test_db, test_user):
        """Test settling a custom bet as lost."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test pick",
            odds=-110.0
        )

        settled_bet = settle_custom_bet(
            db=test_db,
            user_id=test_user.id,
            bet_id=bet.id,
            status="lost",
            payout=-100.0
        )

        assert settled_bet.status == BetStatus.LOST
        assert settled_bet.payout == -100.0

    def test_settle_custom_bet_push(self, test_db, test_user):
        """Test settling a custom bet as push."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test pick",
            odds=-110.0
        )

        settled_bet = settle_custom_bet(
            db=test_db,
            user_id=test_user.id,
            bet_id=bet.id,
            status="push",
            payout=0.0
        )

        assert settled_bet.status == BetStatus.PUSH
        assert settled_bet.payout == 0.0

    def test_settle_custom_bet_invalid_status(self, test_db, test_user):
        """Test settling with invalid status."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test pick",
            odds=-110.0
        )

        with pytest.raises(ValueError, match="Invalid status"):
            settle_custom_bet(
                db=test_db,
                user_id=test_user.id,
                bet_id=bet.id,
                status="invalid",
                payout=0.0
            )

    def test_settle_nonexistent_bet(self, test_db, test_user):
        """Test settling a bet that doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            settle_custom_bet(
                db=test_db,
                user_id=test_user.id,
                bet_id=9999,
                status="won",
                payout=100.0
            )

    def test_settle_other_users_bet(self, test_db, test_user):
        """Test that user cannot settle another user's bet."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test pick",
            odds=-110.0
        )

        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            initial_bankroll=5000.0
        )
        test_db.add(other_user)
        test_db.commit()

        with pytest.raises(ValueError, match="not found"):
            settle_custom_bet(
                db=test_db,
                user_id=other_user.id,
                bet_id=bet.id,
                status="won",
                payout=100.0
            )

    def test_settle_standard_game_bet_fails(self, test_db, test_user, test_game):
        """Test settling a standard game bet (non-custom) should fail."""
        # Create a standard game bet (not custom)
        bet = create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        # Attempting to settle it should raise ValueError
        with pytest.raises(ValueError, match="Cannot manually settle non-custom bet"):
            settle_custom_bet(
                db=test_db,
                user_id=test_user.id,
                bet_id=bet.id,
                status="won",
                payout=100.0
            )


class TestPlaceBetEndpoint:
    """Tests for POST /api/bets endpoint."""

    def test_place_bet_success(self, client, test_db, test_user, test_game, auth_headers):
        """Test successfully placing a bet."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "DraftKings",
                "bet_type": "spread",
                "amount": 100.0,
                "picked_side": "Chiefs"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "bet_id" in data
        assert data["status"] == "pending"
        assert data["amount"] == 100.0
        assert data["picked_side"] == "Chiefs"
        assert data["game_id"] == test_game.id

    def test_place_bet_missing_auth_header(self, client, test_game):
        """Test that bet placement without auth fails."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "DraftKings",
                "bet_type": "spread",
                "amount": 100.0,
                "picked_side": "Chiefs"
            }
        )

        assert response.status_code == 401

    def test_place_bet_invalid_auth_header(self, client, test_game):
        """Test that invalid auth header fails."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "DraftKings",
                "bet_type": "spread",
                "amount": 100.0,
                "picked_side": "Chiefs"
            },
            headers={"Authorization": "invalid"}
        )

        assert response.status_code == 401

    def test_place_bet_invalid_token(self, client, test_game):
        """Test that invalid token fails."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "DraftKings",
                "bet_type": "spread",
                "amount": 100.0,
                "picked_side": "Chiefs"
            },
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401

    def test_place_bet_invalid_sportsbook(self, client, test_game, auth_headers):
        """Test bet placement with invalid sportsbook."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "InvalidBook",
                "bet_type": "spread",
                "amount": 100.0,
                "picked_side": "Chiefs"
            },
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_place_bet_invalid_bet_type(self, client, test_game, auth_headers):
        """Test bet placement with invalid bet type."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "DraftKings",
                "bet_type": "invalid_type",
                "amount": 100.0,
                "picked_side": "Chiefs"
            },
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_place_bet_negative_amount(self, client, test_game, auth_headers):
        """Test bet placement with negative amount."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "DraftKings",
                "bet_type": "spread",
                "amount": -100.0,
                "picked_side": "Chiefs"
            },
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_place_bet_zero_amount(self, client, test_game, auth_headers):
        """Test bet placement with zero amount."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "DraftKings",
                "bet_type": "spread",
                "amount": 0,
                "picked_side": "Chiefs"
            },
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_place_multiple_bets_same_game(self, client, test_db, test_user, test_game, auth_headers):
        """Test that multiple bets on same game are allowed."""
        # First bet
        response1 = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "DraftKings",
                "bet_type": "spread",
                "amount": 100.0,
                "picked_side": "Chiefs"
            },
            headers=auth_headers
        )
        assert response1.status_code == 200
        bet_id_1 = response1.json()["bet_id"]

        # Second bet on same game
        response2 = client.post(
            "/api/bets",
            json={
                "game_id": test_game.id,
                "sportsbook": "FanDuel",
                "bet_type": "moneyline",
                "amount": 50.0,
                "picked_side": "Bills"
            },
            headers=auth_headers
        )
        assert response2.status_code == 200
        bet_id_2 = response2.json()["bet_id"]

        # Verify both bets exist
        assert bet_id_1 != bet_id_2
        assert len(test_db.query(Bet).filter(Bet.user_id == test_user.id).all()) == 2

    def test_place_bet_nonexistent_game(self, client, auth_headers):
        """Test placing bet on non-existent game should fail."""
        response = client.post(
            "/api/bets",
            json={
                "game_id": "nonexistent_game",
                "sportsbook": "DraftKings",
                "bet_type": "spread",
                "amount": 100.0,
                "picked_side": "Chiefs"
            },
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "not found" in response.json()["detail"]


class TestPlaceCustomBetEndpoint:
    """Tests for POST /api/bets/custom endpoint."""

    def test_place_custom_bet_success(self, client, test_user, auth_headers):
        """Test successfully placing a custom bet."""
        response = client.post(
            "/api/bets/custom",
            json={
                "amount": 75.0,
                "picked_side": "Team A to win",
                "odds": +150.0,
                "notes": "Custom pick"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "bet_id" in data
        assert data["status"] == "pending"
        assert data["amount"] == 75.0
        assert data["picked_side"] == "Team A to win"
        assert data["odds_locked_at"] == +150.0
        assert data["notes"] == "Custom pick"
        assert data["game_id"] is None

    def test_place_custom_bet_without_notes(self, client, auth_headers):
        """Test placing custom bet without notes."""
        response = client.post(
            "/api/bets/custom",
            json={
                "amount": 50.0,
                "picked_side": "Player X over 100 yards",
                "odds": -110.0
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] is None

    def test_place_custom_bet_missing_auth(self, client):
        """Test custom bet without auth header."""
        response = client.post(
            "/api/bets/custom",
            json={
                "amount": 75.0,
                "picked_side": "Team A to win",
                "odds": +150.0
            }
        )

        assert response.status_code == 401

    def test_place_custom_bet_invalid_token(self, client):
        """Test custom bet with invalid token."""
        response = client.post(
            "/api/bets/custom",
            json={
                "amount": 75.0,
                "picked_side": "Team A to win",
                "odds": +150.0
            },
            headers={"Authorization": "Bearer invalid.token"}
        )

        assert response.status_code == 401

    def test_place_custom_bet_negative_amount(self, client, auth_headers):
        """Test custom bet with negative amount."""
        response = client.post(
            "/api/bets/custom",
            json={
                "amount": -75.0,
                "picked_side": "Team A to win",
                "odds": +150.0
            },
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_place_custom_bet_zero_amount(self, client, auth_headers):
        """Test custom bet with zero amount."""
        response = client.post(
            "/api/bets/custom",
            json={
                "amount": 0,
                "picked_side": "Team A to win",
                "odds": +150.0
            },
            headers=auth_headers
        )

        assert response.status_code == 422


class TestGetActiveBetsEndpoint:
    """Tests for GET /api/bets/active endpoint."""

    def test_get_active_bets_empty(self, client, auth_headers):
        """Test getting active bets when none exist."""
        response = client.get("/api/bets/active", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_active_bets_success(self, client, test_db, test_user, test_game, auth_headers):
        """Test retrieving active bets."""
        # Create some bets
        create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=75.0,
            picked_side="Custom pick",
            odds=+150.0
        )

        response = client.get("/api/bets/active", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(bet["status"] == "pending" for bet in data)

    def test_get_active_bets_excludes_settled(self, client, test_db, test_user, test_game, auth_headers):
        """Test that settled bets are not included in active list."""
        # Create pending bet
        bet1 = create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        # Create and settle a bet
        bet2 = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=75.0,
            picked_side="Custom pick",
            odds=+150.0
        )
        settle_custom_bet(
            db=test_db,
            user_id=test_user.id,
            bet_id=bet2.id,
            status="won",
            payout=200.0
        )

        response = client.get("/api/bets/active", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["bet_id"] == bet1.id

    def test_get_active_bets_missing_auth(self, client):
        """Test getting active bets without auth."""
        response = client.get("/api/bets/active")
        assert response.status_code == 401

    def test_get_active_bets_other_users_bets_excluded(self, client, test_db, test_user, test_game, auth_headers):
        """Test that other users' bets are not returned."""
        # Create bet for test_user
        create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        # Create another user and their bet
        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            initial_bankroll=5000.0
        )
        test_db.add(other_user)
        test_db.commit()

        create_bet(
            db=test_db,
            user_id=other_user.id,
            game_id=test_game.id,
            sportsbook="FanDuel",
            bet_type="moneyline",
            amount=50.0,
            picked_side="Bills"
        )

        response = client.get("/api/bets/active", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["amount"] == 100.0  # Only test_user's bet


class TestGetBetHistoryEndpoint:
    """Tests for GET /api/bets/history endpoint."""

    def test_get_bet_history_empty(self, client, auth_headers):
        """Test getting history when no settled bets exist."""
        response = client.get("/api/bets/history", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_bet_history_success(self, client, test_db, test_user, auth_headers):
        """Test retrieving bet history."""
        # Create and settle bets
        for status_str in ["won", "lost", "push"]:
            bet = create_custom_bet(
                db=test_db,
                user_id=test_user.id,
                amount=100.0,
                picked_side=f"Pick for {status_str}",
                odds=-110.0
            )
            settle_custom_bet(
                db=test_db,
                user_id=test_user.id,
                bet_id=bet.id,
                status=status_str,
                payout=100.0 if status_str == "won" else 0.0
            )

        response = client.get("/api/bets/history", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        statuses = {bet["status"] for bet in data}
        assert statuses == {"won", "lost", "push"}

    def test_get_bet_history_excludes_pending(self, client, test_db, test_user, test_game, auth_headers):
        """Test that pending bets are excluded from history."""
        # Create pending bet
        create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        # Create settled bet
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=50.0,
            picked_side="Custom",
            odds=-110.0
        )
        settle_custom_bet(
            db=test_db,
            user_id=test_user.id,
            bet_id=bet.id,
            status="won",
            payout=100.0
        )

        response = client.get("/api/bets/history", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "won"

    def test_get_bet_history_missing_auth(self, client):
        """Test getting history without auth."""
        response = client.get("/api/bets/history")
        assert response.status_code == 401

    def test_get_bet_history_other_users_excluded(self, client, test_db, test_user, auth_headers):
        """Test that other users' history is not visible."""
        # Create settled bet for test_user
        bet1 = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Pick 1",
            odds=-110.0
        )
        settle_custom_bet(
            db=test_db,
            user_id=test_user.id,
            bet_id=bet1.id,
            status="won",
            payout=200.0
        )

        # Create another user and settled bet
        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            initial_bankroll=5000.0
        )
        test_db.add(other_user)
        test_db.commit()

        bet2 = create_custom_bet(
            db=test_db,
            user_id=other_user.id,
            amount=50.0,
            picked_side="Pick 2",
            odds=-110.0
        )
        settle_custom_bet(
            db=test_db,
            user_id=other_user.id,
            bet_id=bet2.id,
            status="lost",
            payout=-50.0
        )

        response = client.get("/api/bets/history", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["payout"] == 200.0


class TestGetBetEndpoint:
    """Tests for GET /api/bets/{bet_id} endpoint."""

    def test_get_bet_success(self, client, test_db, test_user, test_game, auth_headers):
        """Test retrieving a specific bet."""
        bet = create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        response = client.get(f"/api/bets/{bet.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["bet_id"] == bet.id
        assert data["status"] == "pending"
        assert data["amount"] == 100.0
        assert data["picked_side"] == "Chiefs"

    def test_get_bet_not_found(self, client, auth_headers):
        """Test retrieving non-existent bet."""
        response = client.get("/api/bets/9999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_bet_other_users_bet(self, client, test_db, test_user, test_game, auth_headers):
        """Test that user cannot view another user's bet."""
        # Create bet for test_user
        bet = create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            initial_bankroll=5000.0
        )
        test_db.add(other_user)
        test_db.commit()

        # Try to access with other user's token
        other_token = create_access_token(other_user.id)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = client.get(f"/api/bets/{bet.id}", headers=other_headers)
        assert response.status_code == 404

    def test_get_bet_missing_auth(self, client, test_db, test_user, test_game):
        """Test getting bet without auth."""
        bet = create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        response = client.get(f"/api/bets/{bet.id}")
        assert response.status_code == 401


class TestSettleBetEndpoint:
    """Tests for PATCH /api/bets/{bet_id}/settle endpoint."""

    def test_settle_bet_won(self, client, test_db, test_user, auth_headers):
        """Test settling a bet as won."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test",
            odds=+100.0
        )

        response = client.patch(
            f"/api/bets/{bet.id}/settle",
            json={"status": "won", "payout": 200.0},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "won"
        assert data["payout"] == 200.0

    def test_settle_bet_lost(self, client, test_db, test_user, auth_headers):
        """Test settling a bet as lost."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test",
            odds=-110.0
        )

        response = client.patch(
            f"/api/bets/{bet.id}/settle",
            json={"status": "lost", "payout": -100.0},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "lost"
        assert data["payout"] == -100.0

    def test_settle_bet_push(self, client, test_db, test_user, auth_headers):
        """Test settling a bet as push."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test",
            odds=-110.0
        )

        response = client.patch(
            f"/api/bets/{bet.id}/settle",
            json={"status": "push", "payout": 0.0},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "push"
        assert data["payout"] == 0.0

    def test_settle_bet_without_payout(self, client, test_db, test_user, auth_headers):
        """Test settling bet without payout."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test",
            odds=-110.0
        )

        response = client.patch(
            f"/api/bets/{bet.id}/settle",
            json={"status": "won"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "won"

    def test_settle_bet_invalid_status(self, client, test_db, test_user, auth_headers):
        """Test settling with invalid status."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test",
            odds=-110.0
        )

        response = client.patch(
            f"/api/bets/{bet.id}/settle",
            json={"status": "invalid"},
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_settle_nonexistent_bet(self, client, auth_headers):
        """Test settling non-existent bet."""
        response = client.patch(
            "/api/bets/9999/settle",
            json={"status": "won"},
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_settle_other_users_bet(self, client, test_db, test_user, auth_headers):
        """Test that user cannot settle another user's bet."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test",
            odds=-110.0
        )

        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            initial_bankroll=5000.0
        )
        test_db.add(other_user)
        test_db.commit()

        other_token = create_access_token(other_user.id)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = client.patch(
            f"/api/bets/{bet.id}/settle",
            json={"status": "won"},
            headers=other_headers
        )

        assert response.status_code == 400

    def test_settle_standard_game_bet_endpoint_fails(self, client, test_db, test_user, test_game, auth_headers):
        """Test that API endpoint rejects settlement of standard game bets."""
        # Create a standard game bet
        bet = create_bet(
            db=test_db,
            user_id=test_user.id,
            game_id=test_game.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs"
        )

        # Attempting to settle via API should fail
        response = client.patch(
            f"/api/bets/{bet.id}/settle",
            json={"status": "won", "payout": 100.0},
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "Cannot manually settle non-custom bet" in response.json()["detail"]

    def test_settle_bet_missing_auth(self, client, test_db, test_user):
        """Test settling without auth."""
        bet = create_custom_bet(
            db=test_db,
            user_id=test_user.id,
            amount=100.0,
            picked_side="Test",
            odds=-110.0
        )

        response = client.patch(
            f"/api/bets/{bet.id}/settle",
            json={"status": "won"}
        )

        assert response.status_code == 401
