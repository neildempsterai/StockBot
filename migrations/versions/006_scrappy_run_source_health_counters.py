"""Scrappy run policy/content counters and source health fetch vs note yield.

Revision ID: 006
Revises: 005
Create Date: 2026-03-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scrappy_runs",
        sa.Column("policy_blocked_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_runs",
        sa.Column("metadata_only_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_runs",
        sa.Column("open_text_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_runs",
        sa.Column("notes_attempted_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_runs",
        sa.Column("notes_rejected_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "scrappy_source_health",
        sa.Column("fetch_success_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_source_health",
        sa.Column("fetch_failure_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_source_health",
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_source_health",
        sa.Column("post_dedup_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_source_health",
        sa.Column("notes_inserted_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scrappy_source_health",
        sa.Column("last_error_code", sa.String(64), nullable=True),
    )
    op.add_column(
        "scrappy_source_health",
        sa.Column("last_error_message", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scrappy_source_health", "last_error_message")
    op.drop_column("scrappy_source_health", "last_error_code")
    op.drop_column("scrappy_source_health", "notes_inserted_count")
    op.drop_column("scrappy_source_health", "post_dedup_count")
    op.drop_column("scrappy_source_health", "candidate_count")
    op.drop_column("scrappy_source_health", "fetch_failure_count")
    op.drop_column("scrappy_source_health", "fetch_success_count")
    op.drop_column("scrappy_runs", "notes_rejected_count")
    op.drop_column("scrappy_runs", "notes_attempted_count")
    op.drop_column("scrappy_runs", "open_text_count")
    op.drop_column("scrappy_runs", "metadata_only_count")
    op.drop_column("scrappy_runs", "policy_blocked_count")
