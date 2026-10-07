"""Retain catalog references when booking service is selected.

Revision ID: 6cd3f421770e
Revises: 5bc2e310669d
"""
from alembic import op, context
import sqlalchemy as sa

revision = "6cd3f421770e"
down_revision = "5bc2e310669d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("booking_events", sa.Column("price_reference", sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Booking price reference verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM booking_events WHERE price_reference IS NOT NULL")).scalar():
        raise RuntimeError("Retained booking price references cannot be removed by downgrade")
    op.drop_column("booking_events", "price_reference")
