"""Guard against the migration chain and the ORM models drifting apart.

Production builds its schema with "alembic upgrade head", but every other
test builds tables from the models via Base.metadata.create_all(). A column
renamed in models.py with no matching migration therefore passed the entire
suite and failed only in production, as bets.odds_at_placement ->
odds_locked_at did. This test compares the two sources directly.
"""

import pathlib

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.models import Base

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_migrations_match_models(tmp_path, monkeypatch):
    """Upgrading a fresh database to head must leave nothing to autogenerate."""
    db_path = str(tmp_path / "migrated.db").replace("\\", "/")
    url = f"sqlite:///{db_path}"

    # env.py builds its engine from Settings, which is lru_cached.
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-migration-check")
    monkeypatch.setenv("ODDSAPI_KEY", "test-key-for-migration-check")

    from app.config import get_settings

    get_settings.cache_clear()
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
        command.upgrade(config, "head")

        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                diff = compare_metadata(context, Base.metadata)
        finally:
            engine.dispose()
    finally:
        get_settings.cache_clear()

    assert diff == [], (
        "Migrations and models disagree. Run "
        "'alembic revision --autogenerate' and commit the result.\n"
        f"Differences: {diff}"
    )
