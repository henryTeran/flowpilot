"""Retained commercial terms for new walk-in cancellation events.

Revision ID: 5bc2e310669d
Revises: 4ab1d209558c
"""
from alembic import op, context
import sqlalchemy as sa

revision = "5bc2e310669d"
down_revision = "4ab1d209558c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("queue_events", sa.Column("cancellation_terms", sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Cancellation terms verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM queue_events WHERE cancellation_terms IS NOT NULL")).scalar():
        raise RuntimeError("Retained cancellation terms cannot be removed by downgrade")
    op.drop_column("queue_events", "cancellation_terms")
