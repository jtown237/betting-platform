# backend/app/main.py
"""FastAPI application entry point with scheduler setup and middleware configuration."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.routers import auth, odds, bets, users
from app.jobs.odds_job import schedule_odds_polling
from app.jobs.scoring_job import schedule_score_polling
from app.jobs.line_locking_job import schedule_line_locking

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown.

    Startup: Initialize and start the APScheduler for background jobs
    Shutdown: Stop the scheduler gracefully
    """
    global scheduler

    # Startup
    try:
        scheduler = AsyncIOScheduler()
        schedule_odds_polling(scheduler)
        schedule_score_polling(scheduler)
        schedule_line_locking(scheduler)
        scheduler.start()
        logger.info("Application startup complete - scheduler started")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise

    yield

    # Shutdown
    if scheduler:
        try:
            scheduler.shutdown(wait=True)
            logger.info("Scheduler shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")


# Create FastAPI app with lifespan context manager
app = FastAPI(
    title="Betting Platform API",
    description="Backend API for betting platform with live odds and auto-settlement",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(odds.router)
app.include_router(bets.router)
app.include_router(users.router)


@app.get("/health")
def health_check():
    """
    Health check endpoint for deployment monitoring.

    Returns:
        dict: Status indicator
    """
    return {"status": "ok"}
