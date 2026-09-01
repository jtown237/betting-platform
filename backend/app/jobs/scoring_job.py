# backend/app/jobs/scoring_job.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.scoring_service import poll_and_settle_scores
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def poll_scores():
    """
    Fetch game scores from ESPN and settle completed bets.
    Runs hourly between 6pm-5am Central Time.
    """
    db = SessionLocal()
    try:
        logger.info("Starting score polling job")
        result = poll_and_settle_scores(db)
        logger.info(f"Score polling result: {result}")
    except Exception as e:
        logger.error(f"Error during score polling: {e}", exc_info=True)
    finally:
        db.close()

def schedule_score_polling(scheduler: AsyncIOScheduler):
    """
    Schedule the score polling job to run hourly between 6pm-5am Central Time.

    The cron schedule "0 18-23,0-5 * * *" means:
    - minute 0
    - hour 18-23 (6pm-11:59pm), 0-5 (midnight-5:59am)
    - every day
    - every month
    - every day of week

    Central Time equivalent: 6pm-5am CT
    """
    try:
        scheduler.add_job(
            poll_scores,
            CronTrigger(hour="18-23,0-5", minute="0"),
            id="score_polling",
            name="Poll ESPN scores and settle bets (6pm-5am CT hourly)",
            replace_existing=True
        )
        logger.info("Score polling job scheduled successfully")
    except Exception as e:
        logger.error(f"Error scheduling score polling job: {e}")
        raise
