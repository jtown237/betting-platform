# backend/app/jobs/odds_job.py
"""Background job for polling odds from OddsAPI every 10 minutes."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
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


def start_odds_scheduler():
    """
    Start the background scheduler for polling odds.
    Should be called once when the application starts.
    """
    scheduler = BackgroundScheduler()

    # Add job to poll odds every 10 minutes
    scheduler.add_job(
        poll_odds,
        trigger=IntervalTrigger(minutes=10),
        id="poll_odds_job",
        name="Poll OddsAPI every 10 minutes",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Started odds polling scheduler")

    return scheduler


def stop_odds_scheduler(scheduler):
    """
    Stop the background scheduler.
    Should be called when the application shuts down.
    """
    if scheduler:
        scheduler.shutdown()
        logger.info("Stopped odds polling scheduler")
