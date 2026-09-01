# backend/app/models.py
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone
import enum

Base = declarative_base()

def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    initial_bankroll = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    bets = relationship("Bet", back_populates="user")

class BetStatus(str, enum.Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    PUSH = "push"

class BetType(str, enum.Enum):
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    OVER_UNDER = "over_under"
    PROP = "prop"
    CUSTOM = "custom"

class Sportsbook(str, enum.Enum):
    DRAFTKINGS = "DraftKings"
    FANDUEL = "FanDuel"
    KALSHI = "Kalshi"
    CUSTOM = "Custom"

class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(String(20), ForeignKey("games.id"), nullable=True)
    sportsbook = Column(Enum(Sportsbook), nullable=False)
    bet_type = Column(Enum(BetType), nullable=False)
    amount = Column(Float, nullable=False)
    picked_side = Column(String(255), nullable=False)
    odds_at_placement = Column(Float, nullable=True)
    status = Column(Enum(BetStatus), default=BetStatus.PENDING)
    payout = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    game_start_time = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="bets")
    game = relationship("Game", back_populates="bets")

class Sport(str, enum.Enum):
    NFL = "NFL"
    CFB = "CFB"

class GameStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"

class Game(Base):
    __tablename__ = "games"

    id = Column(String(20), primary_key=True)
    sport = Column(Enum(Sport), nullable=False)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    start_time = Column(DateTime, nullable=False)
    final_score_home = Column(Integer, nullable=True)
    final_score_away = Column(Integer, nullable=True)
    status = Column(Enum(GameStatus), default=GameStatus.SCHEDULED)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    bets = relationship("Bet", back_populates="game")
    odds = relationship("Odds", back_populates="game")

class Odds(Base):
    __tablename__ = "odds"

    id = Column(Integer, primary_key=True)
    game_id = Column(String(20), ForeignKey("games.id"), nullable=False)
    sportsbook = Column(Enum(Sportsbook), nullable=False)
    bet_type = Column(Enum(BetType), nullable=False)
    line = Column(Float, nullable=False)
    odds = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=utc_now)

    game = relationship("Game", back_populates="odds")

class TeamStats(Base):
    __tablename__ = "team_stats"

    id = Column(Integer, primary_key=True)
    team_id = Column(String(10), nullable=False)
    sport = Column(Enum(Sport), nullable=False)
    season = Column(Integer, nullable=False)
    stat_key = Column(String(100), nullable=False)
    stat_value = Column(Float, nullable=False)
    source = Column(String(100), nullable=True)
    last_updated = Column(DateTime, default=utc_now, onupdate=utc_now)
