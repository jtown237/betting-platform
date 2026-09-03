"""Add MLB to the sport enum

Revision ID: c8f2d0b5e631
Revises: b7e1c9a4d520
Create Date: 2026-09-03 12:41:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c8f2d0b5e631'
down_revision: Union[str, None] = 'b7e1c9a4d520'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite renders Enum as VARCHAR with a CHECK constraint, which the
        # models already describe. Nothing to alter.
        return

    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block on
    # PostgreSQL below 12, and the added value cannot be used in the same
    # transaction that adds it. Commit the migration transaction first.
    op.execute("COMMIT")
    op.execute("ALTER TYPE sport ADD VALUE IF NOT EXISTS 'MLB'")


def downgrade() -> None:
    # PostgreSQL cannot remove a value from an enum type without recreating
    # it and rewriting every dependent column. An unused extra value is
    # harmless, so this is deliberately a no-op.
    pass
