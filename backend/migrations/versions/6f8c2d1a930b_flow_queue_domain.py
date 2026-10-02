"""Add transactional queue events and assignment/cancellation timestamps.

Revision ID: 6f8c2d1a930b
Revises: 3ba965fb2922
"""
from alembic import op
import sqlalchemy as sa

revision = "6f8c2d1a930b"
down_revision = "3ba965fb2922"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("queue_tickets", sa.Column("creation_fingerprint", sa.String(64), nullable=True))
    op.add_column("queue_tickets", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("queue_tickets", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "queue_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("previous_status", sa.String(40), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_queue_events_institute_id", "queue_events", ["institute_id"])
    op.create_index("ix_queue_events_ticket_id", "queue_events", ["ticket_id"])


def downgrade():
    op.drop_table("queue_events")
    op.drop_column("queue_tickets", "cancelled_at")
    op.drop_column("queue_tickets", "assigned_at")
    op.drop_column("queue_tickets", "creation_fingerprint")
