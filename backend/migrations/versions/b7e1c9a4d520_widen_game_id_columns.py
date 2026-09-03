"""Widen game identifier columns to 64 characters

OddsAPI event ids are 32-character hex strings, but the columns were
String(20). SQLite ignores VARCHAR limits, so the whole test suite passed
while Postgres would reject every insert with "value too long for type
character varying(20)" -- meaning no odds could ever be stored.

Revision ID: b7e1c9a4d520
Revises: dc546b783b9a
Create Date: 2026-09-03 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7e1c9a4d520'
down_revision: Union[str, None] = 'dc546b783b9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, nullable) for every column holding a game id.
_ID_COLUMNS = [
    ("games", "id", False),
    ("bets", "game_id", True),
    ("odds", "game_id", False),
]


def upgrade() -> None:
    for table, column, nullable in _ID_COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.String(length=20),
                type_=sa.String(length=64),
                existing_nullable=nullable,
            )


def downgrade() -> None:
    for table, column, nullable in _ID_COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.String(length=64),
                type_=sa.String(length=20),
                existing_nullable=nullable,
            )
