# backend/tests/test_auth.py
import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import JWTError

from app.models import Base, User
from app.database import get_db
from app.routers.auth import router as auth_router
from app.auth import hash_password, verify_password, create_access_token, verify_token
from app.config import get_settings


# Setup test database with file-based SQLite to avoid threading issues
@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test function."""
    # Use a temporary file for SQLite to avoid threading issues with in-memory DB
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
    """Create a test client with the auth router."""
    app = FastAPI()
    app.include_router(auth_router)

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_produces_hash(self):
        """Test that password hashing produces a hash."""
        plain_password = "password"
        hashed = hash_password(plain_password)
        # Just verify that something was produced
        assert isinstance(hashed, str)

    def test_verify_password_with_correct_password(self):
        """Test that correct password verifies."""
        plain_password = "password"
        hashed = hash_password(plain_password)
        assert verify_password(plain_password, hashed) is True

    def test_verify_password_with_incorrect_password(self):
        """Test that incorrect password fails verification."""
        plain_password = "password"
        hashed = hash_password(plain_password)
        assert verify_password("wrongpassword", hashed) is False


class TestJWTTokens:
    """Tests for JWT token creation and verification."""

    def test_create_access_token(self):
        """Test that access token is created."""
        user_id = 123
        token = create_access_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_valid(self):
        """Test that valid token is verified and user_id is extracted."""
        user_id = 123
        token = create_access_token(user_id)

        decoded_user_id = verify_token(token)
        assert decoded_user_id == user_id

    def test_verify_token_invalid(self):
        """Test that invalid token raises JWTError."""
        invalid_token = "invalid.token.here"

        with pytest.raises(JWTError):
            verify_token(invalid_token)

    def test_verify_token_corrupted(self):
        """Test that corrupted token raises JWTError."""
        user_id = 123
        token = create_access_token(user_id)
        corrupted_token = token[:-10] + "1234567890"

        with pytest.raises(JWTError):
            verify_token(corrupted_token)


class TestRegisterEndpoint:
    """Tests for the register endpoint."""

    def test_register_success(self, client, test_db):
        """Test successful user registration."""
        response = client.post("/api/auth/register", json={
            "email": "newuser@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": 1000.0
        })

        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "token" in data
        assert isinstance(data["user_id"], int)
        assert isinstance(data["token"], str)

        # Verify user was created in database
        user = test_db.query(User).filter(User.email == "newuser@example.com").first()
        assert user is not None
        assert user.initial_bankroll == 1000.0

    def test_register_duplicate_email(self, client, test_db):
        """Test that registering with duplicate email fails."""
        # Create first user
        client.post("/api/auth/register", json={
            "email": "duplicate@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": 1000.0
        })

        # Try to create second user with same email
        response = client.post("/api/auth/register", json={
            "email": "duplicate@example.com",
            "password": "DifferentPassword123",
            "initial_bankroll": 2000.0
        })

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client):
        """Test that registration with invalid email fails."""
        response = client.post("/api/auth/register", json={
            "email": "not_an_email",
            "password": "SecurePassword123",
            "initial_bankroll": 1000.0
        })

        assert response.status_code == 422

    def test_register_short_password(self, client):
        """Test that registration with short password fails."""
        response = client.post("/api/auth/register", json={
            "email": "user@example.com",
            "password": "short",
            "initial_bankroll": 1000.0
        })

        assert response.status_code == 422

    def test_register_invalid_bankroll(self, client):
        """Test that registration with invalid bankroll fails."""
        response = client.post("/api/auth/register", json={
            "email": "user@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": -1000.0
        })

        assert response.status_code == 422

    def test_register_zero_bankroll(self, client):
        """Test that registration with zero bankroll fails."""
        response = client.post("/api/auth/register", json={
            "email": "user@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": 0
        })

        assert response.status_code == 422

    def test_register_token_is_valid(self, client, test_db):
        """Test that registered user's token is valid."""
        response = client.post("/api/auth/register", json={
            "email": "tokentest@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": 1000.0
        })

        data = response.json()
        token = data["token"]
        user_id = data["user_id"]

        # Verify token can be decoded
        decoded_user_id = verify_token(token)
        assert decoded_user_id == user_id


class TestLoginEndpoint:
    """Tests for the login endpoint."""

    def test_login_success(self, client, test_db):
        """Test successful user login."""
        # Register user first
        register_response = client.post("/api/auth/register", json={
            "email": "logintest@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": 1000.0
        })
        registered_user_id = register_response.json()["user_id"]

        # Login with correct credentials
        response = client.post("/api/auth/login", json={
            "email": "logintest@example.com",
            "password": "SecurePassword123"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == registered_user_id
        assert "token" in data
        assert isinstance(data["token"], str)

    def test_login_wrong_password(self, client, test_db):
        """Test login with wrong password fails."""
        # Register user first
        client.post("/api/auth/register", json={
            "email": "wrongpass@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": 1000.0
        })

        # Try login with wrong password
        response = client.post("/api/auth/login", json={
            "email": "wrongpass@example.com",
            "password": "WrongPassword123"
        })

        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent email fails."""
        response = client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "SomePassword123"
        })

        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    def test_login_invalid_email_format(self, client):
        """Test login with invalid email format fails."""
        response = client.post("/api/auth/login", json={
            "email": "not_an_email",
            "password": "SomePassword123"
        })

        assert response.status_code == 422

    def test_login_token_is_valid(self, client, test_db):
        """Test that login token is valid."""
        # Register user first
        register_response = client.post("/api/auth/register", json={
            "email": "tokenlogin@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": 1000.0
        })
        registered_user_id = register_response.json()["user_id"]

        # Login and get token
        response = client.post("/api/auth/login", json={
            "email": "tokenlogin@example.com",
            "password": "SecurePassword123"
        })

        data = response.json()
        token = data["token"]

        # Verify token can be decoded
        decoded_user_id = verify_token(token)
        assert decoded_user_id == registered_user_id

    def test_login_case_sensitive_email(self, client, test_db):
        """Test that email comparison is case-sensitive in login."""
        # Register with lowercase email
        client.post("/api/auth/register", json={
            "email": "casesensitive@example.com",
            "password": "SecurePassword123",
            "initial_bankroll": 1000.0
        })

        # Try login with uppercase email (should fail due to case sensitivity)
        response = client.post("/api/auth/login", json={
            "email": "CaseSensitive@example.com",
            "password": "SecurePassword123"
        })

        assert response.status_code == 401
