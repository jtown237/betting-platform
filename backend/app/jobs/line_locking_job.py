# backend/app/jobs/line_locking_job.py
"""Background job for locking betting lines before games start."""

import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_
from app.database import SessionLocal
from app.models import Game, Bet, GameStatus, Odds

logger = logging.getLogger(__name__)


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def lock_lines_for_upcoming_games():
    """
    Lock betting lines for games starting within the next 5 minutes.

    Query all games with start_time within next 5 minutes (upcoming games).
    For each game, update all bets on that game where odds_locked_at is NULL.
    Set odds_at_placement (via odds_locked_at) from the current available odds.
    """
    db = SessionLocal()
    try:
        now = utc_now()
        five_minutes_from_now = now + timedelta(minutes=5)

        # Query games starting within next 5 minutes
        upcoming_games = db.query(Game).filter(
            and_(
                Game.start_time > now,
                Game.start_time <= five_minutes_from_now,
                Game.status == GameStatus.SCHEDULED
            )
        ).all()

        if not upcoming_games:
            logger.info("No upcoming games found for line locking")
            return {"games_processed": 0, "bets_updated": 0}

        logger.info(f"Found {len(upcoming_games)} games starting within 5 minutes")

        total_bets_updated = 0

        for game in upcoming_games:
            try:
                # Query all pending bets on this game where odds_locked_at is NULL
                bets_to_lock = db.query(Bet).filter(
                    and_(
                        Bet.game_id == game.id,
                        Bet.odds_locked_at == None
                    )
                ).all()

                if not bets_to_lock:
                    logger.info(f"No bets to lock for game {game.id}")
                    continue

                logger.info(f"Locking odds for {len(bets_to_lock)} bets on game {game.id}")

                # For each bet, find the corresponding odds and lock them
                for bet in bets_to_lock:
                    try:
                        # Query matching odds from the same sportsbook
                        matching_odds = db.query(Odds).filter(
                            and_(
                                Odds.game_id == game.id,
                                Odds.sportsbook == bet.sportsbook,
                                Odds.bet_type == bet.bet_type
                            )
                        ).order_by(Odds.timestamp.desc()).first()

                        if matching_odds:
                            # Lock the odds at the current value
                            bet.odds_locked_at = matching_odds.odds
                            logger.info(
                                f"Locked odds for bet {bet.id}: {matching_odds.odds} "
                                f"({matching_odds.bet_type.value})"
                            )
                            total_bets_updated += 1
                        else:
                            logger.warning(
                                f"No matching odds found for bet {bet.id} "
                                f"(sportsbook: {bet.sportsbook}, type: {bet.bet_type})"
                            )

                    except Exception as e:
                        logger.error(f"Error locking odds for bet {bet.id}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error processing game {game.id} for line locking: {e}")
                continue

        # Commit all changes
        if total_bets_updated > 0:
            db.commit()
            logger.info(f"Line locking complete: {total_bets_updated} bets updated")

        return {
            "games_processed": len(upcoming_games),
            "bets_updated": total_bets_updated
        }

    except Exception as e:
        logger.error(f"Error in line locking job: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()


def schedule_line_locking(scheduler: AsyncIOScheduler):
    """
    Schedule the line locking job to run every 1 minute.

    This ensures lines are locked ~2 minutes before games start (the job runs every minute,
    and we check for games within the next 5 minutes).

    Args:
        scheduler: AsyncIOScheduler instance to add the job to
    """
    try:
        scheduler.add_job(
            lock_lines_for_upcoming_games,
            trigger=IntervalTrigger(minutes=1),
            id="line_locking_job",
            name="Lock betting lines for upcoming games (every 1 minute)",
            replace_existing=True
        )
        logger.info("Line locking job scheduled successfully")
    except Exception as e:
        logger.error(f"Error scheduling line locking job: {e}")
        raise
