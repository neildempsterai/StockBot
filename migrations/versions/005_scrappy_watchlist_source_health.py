"""Scrappy watchlist_symbols and scrappy_source_health.

Revision ID: 005
Revises: 004
Create Date: 2026-03-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist_symbols",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watchlist_symbols_symbol", "watchlist_symbols", ["symbol"], unique=True)

    op.create_table(
        "scrappy_source_health",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrappy_source_health_source_name", "scrappy_source_health", ["source_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_scrappy_source_health_source_name", table_name="scrappy_source_health")
    op.drop_table("scrappy_source_health")
    op.drop_index("ix_watchlist_symbols_symbol", table_name="watchlist_symbols")
    op.drop_table("watchlist_symbols")
