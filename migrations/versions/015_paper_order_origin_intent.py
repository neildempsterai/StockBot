"""Paper order origin and intent (strategy vs operator_test).

Revision ID: 015
Revises: 014
Create Date: 2026-03-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("paper_orders", sa.Column("order_origin", sa.String(32), nullable=True))
    op.add_column("paper_orders", sa.Column("order_intent", sa.String(32), nullable=True))
    op.add_column("paper_orders", sa.Column("note", sa.Text(), nullable=True))
    op.execute("UPDATE paper_orders SET order_origin = 'strategy' WHERE order_origin IS NULL")
    op.alter_column(
        "paper_orders",
        "order_origin",
        existing_type=sa.String(32),
        nullable=False,
        server_default="strategy",
    )


def downgrade() -> None:
    op.drop_column("paper_orders", "note")
    op.drop_column("paper_orders", "order_intent")
    op.drop_column("paper_orders", "order_origin")
