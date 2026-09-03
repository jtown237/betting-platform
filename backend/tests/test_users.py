"""Tests for user profile endpoint and router."""

import pytest
import tempfile
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models import Base, User, Bet, BetStatus
from app.auth import create_access_token
from app.routers import users


@pytest.fixture(scope="function")
def test_db():
    """Create a file-based SQLite database for testing."""
    # Use a temporary file for SQLite to avoid threading issues
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
    """Create a test client with the users router."""
    app = FastAPI()
    app.include_router(users.router)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


class TestUserProfile:
    """Tests for GET /api/user/profile endpoint."""

    def test_profile_without_auth(self, client, test_db):
        """Test profile endpoint without authorization header."""
        response = client.get("/api/user/profile")
        assert response.status_code == 401
        assert "Authorization header missing" in response.json()["detail"]

    def test_profile_invalid_auth_header(self, client, test_db):
        """Test profile endpoint with invalid authorization header format."""
        response = client.get(
            "/api/user/profile",
            headers={"Authorization": "InvalidFormat"}
        )
        assert response.status_code == 401
        assert "Invalid authorization header format" in response.json()["detail"]

    def test_profile_invalid_token(self, client, test_db):
        """Test profile endpoint with invalid token."""
        response = client.get(
            "/api/user/profile",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]

    def test_profile_user_not_found(self, client, test_db):
        """Test profile endpoint with valid token but non-existent user."""
        token = create_access_token(user_id=999)
        response = client.get(
            "/api/user/profile",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_profile_success(self, client, test_db):
        """Test successful profile retrieval."""
        # Create a user with a simple hash (avoid bcrypt issues)
        user = User(
            email="test@example.com",
            password_hash="$2b$12$test_hash",
            initial_bankroll=1000.0
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        # Create a token
        token = create_access_token(user.id)

        # Get profile
        response = client.get(
            "/api/user/profile",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["initial_bankroll"] == 1000.0
        # Nothing staked yet, so there is nothing to have a return on.
        assert data["total_returns"] == 0.0
        assert data["total_bets"] == 0
        assert data["bets_won"] == 0
        assert data["bets_lost"] == 0
        assert data["bets_push"] == 0
        assert data["roi_percent"] == 0.0

    def test_profile_with_bets(self, client, test_db):
        """Test profile endpoint with multiple bets."""
        # Create a user with a simple hash (avoid bcrypt issues)
        user = User(
            email="test@example.com",
            password_hash="$2b$12$test_hash",
            initial_bankroll=1000.0
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        # Create some bets with different statuses
        bet_won = Bet(
            user_id=user.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs",
            status=BetStatus.WON,
            payout=190.0
        )
        bet_lost = Bet(
            user_id=user.id,
            sportsbook="FanDuel",
            bet_type="moneyline",
            amount=50.0,
            picked_side="Bills",
            status=BetStatus.LOST,
            payout=0.0
        )
        bet_pending = Bet(
            user_id=user.id,
            sportsbook="DraftKings",
            bet_type="over_under",
            amount=75.0,
            picked_side="Over 45.5",
            status=BetStatus.PENDING,
            payout=None
        )
        test_db.add_all([bet_won, bet_lost, bet_pending])
        test_db.commit()

        # Create a token
        token = create_access_token(user.id)

        # Get profile
        response = client.get(
            "/api/user/profile",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["initial_bankroll"] == 1000.0
        assert data["total_bets"] == 3
        assert data["bets_won"] == 1
        assert data["bets_lost"] == 1
        assert data["bets_push"] == 0
        # Settled: won (100 staked -> 190) and lost (50 staked -> 0).
        # The 75 pending is excluded from both staked and payouts.
        # returns = 190 - 150 = 40
        assert data["total_returns"] == 40.0
        # roi = 40 / 150 * 100
        assert data["roi_percent"] == pytest.approx(26.6666666, rel=1e-6)

    def test_profile_with_push_bets(self, client, test_db):
        """Test profile endpoint with push bets."""
        # Create a user with a simple hash (avoid bcrypt issues)
        user = User(
            email="test@example.com",
            password_hash="$2b$12$test_hash",
            initial_bankroll=500.0
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        # Create a push bet
        bet_push = Bet(
            user_id=user.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs",
            status=BetStatus.PUSH,
            payout=100.0  # Stake returned
        )
        test_db.add(bet_push)
        test_db.commit()

        # Create a token
        token = create_access_token(user.id)

        # Get profile
        response = client.get(
            "/api/user/profile",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["bets_push"] == 1
        # A push returns the stake, so it nets exactly zero.
        assert data["total_returns"] == 0.0
        assert data["roi_percent"] == 0.0

    def test_profile_only_pending_bets(self, client, test_db):
        """Pending bets are counted but must not be treated as a loss."""
        user = User(
            email="test@example.com",
            password_hash="$2b$12$test_hash",
            initial_bankroll=1000.0
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        test_db.add(Bet(
            user_id=user.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=200.0,
            picked_side="Chiefs",
            status=BetStatus.PENDING,
            payout=None
        ))
        test_db.commit()

        token = create_access_token(user.id)
        response = client.get(
            "/api/user/profile",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_bets"] == 1
        # Nothing has settled, so no return has been realised either way.
        assert data["total_returns"] == 0.0
        assert data["roi_percent"] == 0.0

    def test_profile_positive_roi(self, client, test_db):
        """Test profile endpoint with positive ROI."""
        # Create a user with a simple hash (avoid bcrypt issues)
        user = User(
            email="test@example.com",
            password_hash="$2b$12$test_hash",
            initial_bankroll=1000.0
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        # Create winning bets
        bet_won = Bet(
            user_id=user.id,
            sportsbook="DraftKings",
            bet_type="spread",
            amount=100.0,
            picked_side="Chiefs",
            status=BetStatus.WON,
            payout=250.0
        )
        test_db.add(bet_won)
        test_db.commit()

        # Create a token
        token = create_access_token(user.id)

        # Get profile
        response = client.get(
            "/api/user/profile",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        # 100 staked returned 250, so profit is 150 on 100 staked.
        assert data["total_returns"] == 150.0
        assert data["roi_percent"] == pytest.approx(150.0)


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
