# backend/tests/test_scoring.py
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
from app.models import (
    Base, User, Game, Bet, Odds, BetStatus, BetType,
    Sportsbook, Sport, GameStatus
)
from app.services.scoring_service import (
    fetch_game_score, settle_bets_for_game, calculate_payout,
    settle_spread_bet, settle_moneyline_bet, settle_over_under_bet,
    poll_and_settle_scores
)

def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

@pytest.fixture
def test_db():
    """Create in-memory SQLite test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def test_user(test_db):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        initial_bankroll=1000.0
    )
    test_db.add(user)
    test_db.commit()
    return user

@pytest.fixture
def test_game(test_db):
    """Create a test game"""
    game = Game(
        id="401547382",
        sport=Sport.NFL,
        home_team="Kansas City Chiefs",
        away_team="Buffalo Bills",
        start_time=utc_now() - timedelta(hours=3),
        status=GameStatus.LIVE
    )
    test_db.add(game)
    test_db.commit()
    return game

@pytest.fixture
def test_odds(test_db, test_game):
    """Create test odds"""
    spread_odds = Odds(
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.SPREAD,
        line=-3.0,
        odds=-110
    )
    moneyline_odds = Odds(
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.MONEYLINE,
        line=None,
        odds=-150
    )
    over_under_odds = Odds(
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.OVER_UNDER,
        line=45.5,
        odds=-110
    )
    test_db.add_all([spread_odds, moneyline_odds, over_under_odds])
    test_db.commit()
    return spread_odds

# Tests for calculate_payout
def test_calculate_payout_negative_odds():
    """Test payout calculation with negative odds"""
    # -110 odds: bet $110 to win $100
    payout = calculate_payout(110.0, -110, True)
    assert payout == 210.0  # $110 + $100 winnings

def test_calculate_payout_positive_odds():
    """Test payout calculation with positive odds"""
    # +200 odds: $100 bet wins $200
    payout = calculate_payout(100.0, 200, True)
    assert payout == 300.0  # $100 + $200 winnings

def test_calculate_payout_loss():
    """Test payout when bet loses"""
    payout = calculate_payout(100.0, -110, False)
    assert payout == 0.0

# Tests for spread settlement
def test_settle_spread_bet_home_wins():
    """Test spread bet settlement when home team wins"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    # Home -3.0, home scores 20, away scores 10
    # Home wins by 10, which beats the -3 spread
    status, payout = settle_spread_bet(bet, 20, 10, "Chiefs -3.0", -110)
    assert status == BetStatus.WON
    assert abs(payout - 190.91) < 0.01  # 100 + (100 * 100 / 110)

def test_settle_spread_bet_away_wins():
    """Test spread bet settlement when away team wins"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    # Home -3.0, home scores 20, away scores 30
    # Away wins, away covered the +3 spread
    status, payout = settle_spread_bet(bet, 20, 30, "Bills +3.0", -110)
    assert status == BetStatus.WON
    assert abs(payout - 190.91) < 0.01

def test_settle_spread_bet_push():
    """Test spread bet settlement on a push"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    # Home -3.0, home scores 20, away scores 17
    # Exact spread hit = push
    status, payout = settle_spread_bet(bet, 20, 17, "Chiefs -3.0", -110)
    assert status == BetStatus.PUSH
    assert payout == 100.0  # Return stake

# Tests for moneyline settlement
def test_settle_moneyline_bet_home_win():
    """Test moneyline bet when home team wins"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    status, payout = settle_moneyline_bet(bet, 20, 10, "home", -150)
    assert status == BetStatus.WON

def test_settle_moneyline_bet_away_win():
    """Test moneyline bet when away team wins"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    status, payout = settle_moneyline_bet(bet, 10, 20, "away", +150)
    assert status == BetStatus.WON

def test_settle_moneyline_bet_loss():
    """Test moneyline bet loss"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    status, payout = settle_moneyline_bet(bet, 20, 10, "away", +150)
    assert status == BetStatus.LOST
    assert payout == 0.0

def test_settle_moneyline_bet_push():
    """Test moneyline bet on a tie (push)"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    status, payout = settle_moneyline_bet(bet, 20, 20, "home", -150)
    assert status == BetStatus.PUSH
    assert payout == 100.0

# Tests for over/under settlement
def test_settle_over_under_bet_over_wins():
    """Test over/under bet when over is hit"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    # Total is 45.5, combined score is 51 (over)
    status, payout = settle_over_under_bet(bet, 27, 24, "Over 45.5", -110)
    assert status == BetStatus.WON

def test_settle_over_under_bet_under_wins():
    """Test over/under bet when under is hit"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    # Total is 45.5, combined score is 40 (under)
    status, payout = settle_over_under_bet(bet, 20, 20, "Under 45.5", -110)
    assert status == BetStatus.WON

def test_settle_over_under_bet_push():
    """Test over/under bet on exact total (push)"""
    bet = MagicMock()
    bet.amount = 100.0
    bet.id = 1

    # Total is 45.5, combined score is 45.5 (push)
    status, payout = settle_over_under_bet(bet, 23, 22.5, "Over 45.5", -110)
    assert status == BetStatus.PUSH
    assert payout == 100.0

# Integration tests
def test_settle_bets_for_game_spread(test_db, test_user, test_game):
    """Test settling spread bets for a game"""
    # Create a spread bet
    bet = Bet(
        user_id=test_user.id,
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.SPREAD,
        amount=100.0,
        picked_side="Chiefs -3.0",
        odds_locked_at=-110,
        status=BetStatus.PENDING,
        game_start_time=utc_now()
    )
    test_db.add(bet)
    test_db.commit()

    # Settle with Chiefs winning by more than 3
    result = settle_bets_for_game(test_db, test_game.id, 20, 10)

    # Verify bet was settled
    updated_bet = test_db.query(Bet).filter(Bet.id == bet.id).first()
    assert updated_bet.status == BetStatus.WON
    assert updated_bet.payout is not None
    assert result["won"] == 1

def test_settle_bets_for_game_moneyline(test_db, test_user, test_game):
    """Test settling moneyline bets for a game"""
    bet = Bet(
        user_id=test_user.id,
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.MONEYLINE,
        amount=100.0,
        picked_side="home",
        odds_locked_at=-150,
        status=BetStatus.PENDING,
        game_start_time=utc_now()
    )
    test_db.add(bet)
    test_db.commit()

    # Settle with home team winning
    result = settle_bets_for_game(test_db, test_game.id, 20, 10)

    updated_bet = test_db.query(Bet).filter(Bet.id == bet.id).first()
    assert updated_bet.status == BetStatus.WON
    assert result["won"] == 1

def test_settle_bets_for_game_over_under(test_db, test_user, test_game):
    """Test settling over/under bets for a game"""
    bet = Bet(
        user_id=test_user.id,
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.OVER_UNDER,
        amount=100.0,
        picked_side="Over 45.5",
        odds_locked_at=-110,
        status=BetStatus.PENDING,
        game_start_time=utc_now()
    )
    test_db.add(bet)
    test_db.commit()

    # Settle with combined score over the total
    result = settle_bets_for_game(test_db, test_game.id, 27, 24)

    updated_bet = test_db.query(Bet).filter(Bet.id == bet.id).first()
    assert updated_bet.status == BetStatus.WON
    assert result["won"] == 1

def test_settle_bets_for_game_multiple_bets(test_db, test_user, test_game):
    """Test settling multiple bets for a game"""
    # Create multiple bets
    bet1 = Bet(
        user_id=test_user.id,
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.SPREAD,
        amount=100.0,
        picked_side="Chiefs -3.0",
        odds_locked_at=-110,
        status=BetStatus.PENDING,
        game_start_time=utc_now()
    )
    bet2 = Bet(
        user_id=test_user.id,
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.MONEYLINE,
        amount=50.0,
        picked_side="away",
        odds_locked_at=+150,
        status=BetStatus.PENDING,
        game_start_time=utc_now()
    )
    test_db.add_all([bet1, bet2])
    test_db.commit()

    # Settle with Chiefs winning (bet1 wins, bet2 loses)
    result = settle_bets_for_game(test_db, test_game.id, 20, 10)

    assert result["won"] == 1
    assert result["lost"] == 1

def test_settle_bets_for_game_custom_bet_skipped(test_db, test_user, test_game):
    """Test that custom bets are not auto-settled"""
    bet = Bet(
        user_id=test_user.id,
        game_id=test_game.id,
        sportsbook=Sportsbook.CUSTOM,
        bet_type=BetType.CUSTOM,
        amount=50.0,
        picked_side="Player to score TD",
        odds_locked_at=-110,
        status=BetStatus.PENDING
    )
    test_db.add(bet)
    test_db.commit()

    # Try to settle
    result = settle_bets_for_game(test_db, test_game.id, 20, 10)

    # Custom bet should remain pending
    updated_bet = test_db.query(Bet).filter(Bet.id == bet.id).first()
    assert updated_bet.status == BetStatus.PENDING

# API mocking tests
@patch("app.services.scoring_service.requests.get")
def test_fetch_game_score_success(mock_get):
    """Test successful ESPN API call"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": 20},
                {"homeAway": "away", "score": 10}
            ]
        }],
        "status": {"type": "Final"}
    }
    mock_get.return_value = mock_response

    result = fetch_game_score("401547382")
    assert result["home_score"] == 20
    assert result["away_score"] == 10
    assert result["status"] == GameStatus.COMPLETED.value

@patch("app.services.scoring_service.requests.get")
def test_fetch_game_score_live(mock_get):
    """Test ESPN API call for live game"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": 14},
                {"homeAway": "away", "score": 7}
            ]
        }],
        "status": {"type": "In Progress"}
    }
    mock_get.return_value = mock_response

    result = fetch_game_score("401547382")
    assert result["status"] == GameStatus.LIVE.value

@patch("app.services.scoring_service.requests.get")
def test_fetch_game_score_error(mock_get):
    """Test ESPN API call failure"""
    mock_get.side_effect = Exception("API Error")

    with pytest.raises(Exception):
        fetch_game_score("401547382")

# Full workflow test
@patch("app.services.scoring_service.fetch_game_score")
def test_poll_and_settle_scores(mock_fetch, test_db, test_user, test_game):
    """Test complete polling and settlement workflow"""
    # Mock ESPN API response
    mock_fetch.return_value = {
        "home_score": 20,
        "away_score": 10,
        "status": GameStatus.COMPLETED.value
    }

    # Create a pending bet
    bet = Bet(
        user_id=test_user.id,
        game_id=test_game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.SPREAD,
        amount=100.0,
        picked_side="Chiefs -3.0",
        odds_locked_at=-110,
        status=BetStatus.PENDING,
        game_start_time=utc_now()
    )
    test_db.add(bet)
    test_db.commit()

    # Run polling
    result = poll_and_settle_scores(test_db)

    assert result["games_checked"] == 1
    assert result["games_settled"] == 1
    assert result["total_bets_settled"] == 1

    # Verify game status updated
    updated_game = test_db.query(Game).filter(Game.id == test_game.id).first()
    assert updated_game.status == GameStatus.COMPLETED
    assert updated_game.final_score_home == 20
    assert updated_game.final_score_away == 10

    # Verify bet settled
    updated_bet = test_db.query(Bet).filter(Bet.id == bet.id).first()
    assert updated_bet.status == BetStatus.WON
