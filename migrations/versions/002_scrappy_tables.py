"""Scrappy market-intel tables: scrappy_urls, scrappy_runs, market_intel_notes.

Revision ID: 002
Revises: 001
Create Date: 2026-03-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrappy_urls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("normalized_url", sa.String(2048), nullable=False),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("relevant", sa.Boolean(), nullable=True),
        sa.Column("last_drop_reason", sa.String(64), nullable=True),
        sa.Column("symbol_tags", JSONB(), nullable=True),
        sa.Column("theme_tags", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrappy_urls_url_hash", "scrappy_urls", ["url_hash"], unique=True)
    op.create_index("ix_scrappy_urls_normalized_url", "scrappy_urls", ["normalized_url"], unique=False)
    op.create_index("ix_scrappy_urls_source_name", "scrappy_urls", ["source_name"], unique=False)

    op.create_table(
        "scrappy_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("run_type", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_code", sa.String(32), nullable=True),
        sa.Column("candidate_url_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("post_dedup_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("drop_reason_counts", JSONB(), nullable=True),
        sa.Column("model_provider", sa.String(64), nullable=True),
        sa.Column("selected_model", sa.String(128), nullable=True),
        sa.Column("actual_model_used", sa.String(128), nullable=True),
        sa.Column("selection_reason", sa.String(128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrappy_runs_run_id", "scrappy_runs", ["run_id"], unique=True)
    op.create_index("ix_scrappy_runs_run_type", "scrappy_runs", ["run_type"], unique=False)

    op.create_table(
        "market_intel_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("note_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence_snippets", JSONB(), nullable=True),
        sa.Column("detected_symbols", JSONB(), nullable=True),
        sa.Column("primary_symbol", sa.String(32), nullable=True),
        sa.Column("sector_tags", JSONB(), nullable=True),
        sa.Column("theme_tags", JSONB(), nullable=True),
        sa.Column("catalyst_type", sa.String(64), nullable=True),
        sa.Column("sentiment_label", sa.String(32), nullable=True),
        sa.Column("sentiment_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_metadata", JSONB(), nullable=True),
        sa.Column("scrappy_run_id", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_intel_notes_note_id", "market_intel_notes", ["note_id"], unique=True)
    op.create_index("ix_market_intel_notes_source_name", "market_intel_notes", ["source_name"], unique=False)
    op.create_index("ix_market_intel_notes_primary_symbol", "market_intel_notes", ["primary_symbol"], unique=False)
    op.create_index("ix_market_intel_notes_catalyst_type", "market_intel_notes", ["catalyst_type"], unique=False)
    op.create_index("ix_market_intel_notes_scrappy_run_id", "market_intel_notes", ["scrappy_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_market_intel_notes_scrappy_run_id", table_name="market_intel_notes")
    op.drop_index("ix_market_intel_notes_catalyst_type", table_name="market_intel_notes")
    op.drop_index("ix_market_intel_notes_primary_symbol", table_name="market_intel_notes")
    op.drop_index("ix_market_intel_notes_source_name", table_name="market_intel_notes")
    op.drop_index("ix_market_intel_notes_note_id", table_name="market_intel_notes")
    op.drop_table("market_intel_notes")
    op.drop_index("ix_scrappy_runs_run_type", table_name="scrappy_runs")
    op.drop_index("ix_scrappy_runs_run_id", table_name="scrappy_runs")
    op.drop_table("scrappy_runs")
    op.drop_index("ix_scrappy_urls_source_name", table_name="scrappy_urls")
    op.drop_index("ix_scrappy_urls_normalized_url", table_name="scrappy_urls")
    op.drop_index("ix_scrappy_urls_url_hash", table_name="scrappy_urls")
    op.drop_table("scrappy_urls")
