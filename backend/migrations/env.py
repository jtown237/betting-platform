# backend/migrations/env.py
from sqlalchemy import create_engine, pool
from alembic import context
from app.models import Base
from app.config import get_settings

settings = get_settings()

config = context.config

target_metadata = Base.metadata

# The URL is taken straight from settings rather than written into the ini
# section: ConfigParser applies %-interpolation, which corrupts generated
# passwords that contain a literal % character.

def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = create_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
