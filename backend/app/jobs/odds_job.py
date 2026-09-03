# backend/app/jobs/odds_job.py
"""Background job for polling odds from OddsAPI every 10 minutes."""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.database import SessionLocal
from app.services.odds_service import fetch_odds_from_api, store_odds

logger = logging.getLogger(__name__)

# Sports to poll
SPORTS_TO_POLL = [
    "americanfootball_nfl",
    "americanfootball_ncaaf"
]


def poll_odds():
    """
    Poll odds from OddsAPI for all supported sports and store in database.
    This function is called periodically by the scheduler.
    """
    db = SessionLocal()
    try:
        for sport in SPORTS_TO_POLL:
            try:
                logger.info(f"Polling odds for {sport}")
                odds_data = fetch_odds_from_api(sport)
                count = store_odds(db, odds_data, sport)
                logger.info(f"Successfully stored {count} odds records for {sport}")
            except Exception as e:
                logger.error(f"Failed to poll odds for {sport}: {e}")
                # Continue with next sport instead of failing completely
                continue
    finally:
        db.close()


def schedule_odds_polling(scheduler: AsyncIOScheduler):
    """
    Schedule the odds polling job to run every 10 minutes.

    Args:
        scheduler: AsyncIOScheduler instance to add the job to
    """
    try:
        scheduler.add_job(
            poll_odds,
            trigger=IntervalTrigger(minutes=10),
            id="poll_odds_job",
            name="Poll OddsAPI every 10 minutes",
            replace_existing=True,
            # Without this the first poll is one full interval away, so every
            # redeploy restarts the clock and leaves the board empty for ten
            # minutes.
            next_run_time=datetime.now(timezone.utc)
        )
        logger.info("Odds polling job scheduled successfully")
    except Exception as e:
        logger.error(f"Error scheduling odds polling job: {e}")
        raise
