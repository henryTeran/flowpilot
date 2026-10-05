"""Preserve booked intervals separately from execution facts.

Revision ID: c4e780bd219a
Revises: b3d620a481f9
"""
from alembic import op
import sqlalchemy as sa

revision = "c4e780bd219a"
down_revision = "b3d620a481f9"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("booked_start_time", "booked_end_time", "actual_start_time", "actual_end_time"):
        op.add_column("appointments", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    # Legacy execution timestamps cannot be reconstructed honestly.
    op.execute("UPDATE appointments SET booked_start_time = start_time, booked_end_time = end_time")


def downgrade():
    with op.batch_alter_table("appointments") as batch:
        for name in ("actual_end_time", "actual_start_time", "booked_end_time", "booked_start_time"):
            batch.drop_column(name)
