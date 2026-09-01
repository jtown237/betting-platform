# backend/tests/test_models.py
from datetime import datetime, timezone
from app.models import User, Bet, Game, Odds, TeamStats, BetStatus, BetType, Sportsbook, Sport, GameStatus

def test_user_creation(test_db):
    user = User(email="test@example.com", password_hash="hash", initial_bankroll=1000.0)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    assert user.id is not None
    assert user.email == "test@example.com"

def test_user_total_returns_field(test_db):
    user = User(email="test@example.com", password_hash="hash", initial_bankroll=1000.0)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    assert hasattr(user, "total_returns")
    assert user.total_returns is None

    # Test setting total_returns
    user.total_returns = 150.0
    test_db.commit()
    test_db.refresh(user)
    assert user.total_returns == 150.0

def test_game_creation(test_db):
    game = Game(
        id="401547382",
        sport=Sport.NFL,
        home_team="Chiefs",
        away_team="Bills",
        start_time=datetime.now(timezone.utc),
        status=GameStatus.SCHEDULED
    )
    test_db.add(game)
    test_db.commit()
    test_db.refresh(game)
    assert game.id == "401547382"
    assert game.sport == Sport.NFL

def test_bet_creation(test_db):
    user = User(email="test@example.com", password_hash="hash", initial_bankroll=1000.0)
    game = Game(
        id="401547382",
        sport=Sport.NFL,
        home_team="Chiefs",
        away_team="Bills",
        start_time=datetime.now(timezone.utc),
        status=GameStatus.SCHEDULED
    )
    test_db.add(user)
    test_db.add(game)
    test_db.commit()

    bet = Bet(
        user_id=user.id,
        game_id=game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.SPREAD,
        amount=100.0,
        picked_side="Chiefs -3",
        status=BetStatus.PENDING
    )
    test_db.add(bet)
    test_db.commit()
    test_db.refresh(bet)
    assert bet.id is not None
    assert bet.status == BetStatus.PENDING

def test_odds_creation(test_db):
    game = Game(
        id="401547382",
        sport=Sport.NFL,
        home_team="Chiefs",
        away_team="Bills",
        start_time=datetime.now(timezone.utc),
        status=GameStatus.SCHEDULED
    )
    test_db.add(game)
    test_db.commit()

    odds = Odds(
        game_id=game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.SPREAD,
        line=-3.0,
        odds=-110
    )
    test_db.add(odds)
    test_db.commit()
    test_db.refresh(odds)
    assert odds.line == -3.0

def test_odds_game_start_time_field(test_db):
    game = Game(
        id="401547382",
        sport=Sport.NFL,
        home_team="Chiefs",
        away_team="Bills",
        start_time=datetime.now(timezone.utc),
        status=GameStatus.SCHEDULED
    )
    test_db.add(game)
    test_db.commit()

    odds = Odds(
        game_id=game.id,
        sportsbook=Sportsbook.DRAFTKINGS,
        bet_type=BetType.SPREAD,
        line=-3.0,
        odds=-110
    )
    test_db.add(odds)
    test_db.commit()
    test_db.refresh(odds)
    assert hasattr(odds, "game_start_time")
    assert odds.game_start_time is None

    # Test setting game_start_time
    game_start = datetime(2026, 9, 1, 20, 0, 0)
    odds.game_start_time = game_start
    test_db.commit()
    test_db.refresh(odds)
    assert odds.game_start_time == game_start

def test_teamstats_creation(test_db):
    stats = TeamStats(
        team_id="KC",
        sport=Sport.NFL,
        season=2025,
        stat_key="off_efficiency",
        stat_value=105.5,
        source="Pro Football Reference"
    )
    test_db.add(stats)
    test_db.commit()
    test_db.refresh(stats)
    assert stats.id is not None
    assert stats.team_id == "KC"
    assert stats.stat_value == 105.5
