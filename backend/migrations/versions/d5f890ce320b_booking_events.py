"""Durable booking history; no fabricated historical events.

Revision ID: d5f890ce320b
Revises: c4e780bd219a
"""
from alembic import op
import sqlalchemy as sa

revision = "d5f890ce320b"
down_revision = "c4e780bd219a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("booking_events",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("appointment_id", sa.String(80), sa.ForeignKey("appointments.id"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=False))
    for column in ("institute_id", "appointment_id"):
        op.create_index(f"ix_booking_events_{column}", "booking_events", [column])


def downgrade():
    op.drop_table("booking_events")
