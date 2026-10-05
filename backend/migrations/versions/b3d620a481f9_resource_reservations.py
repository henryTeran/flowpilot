"""Durable resource interval ownership.

Revision ID: b3d620a481f9
Revises: a1c935e720d4
"""
from alembic import op
import sqlalchemy as sa

revision = "b3d620a481f9"
down_revision = "a1c935e720d4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("resource_reservations",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("resource_id", sa.String(80), sa.ForeignKey("resources.id"), nullable=False),
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), nullable=True),
        sa.Column("appointment_id", sa.String(80), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.CheckConstraint("(ticket_id IS NOT NULL AND appointment_id IS NULL) OR (ticket_id IS NULL AND appointment_id IS NOT NULL)", name="ck_resource_reservation_owner"),
        sa.CheckConstraint("end_time > start_time", name="ck_resource_reservation_interval"),
        sa.CheckConstraint("status IN ('reserved','in_use','released')", name="ck_resource_reservation_status"))
    for column in ("institute_id", "resource_id", "ticket_id", "appointment_id"):
        op.create_index(f"ix_resource_reservations_{column}", "resource_reservations", [column])


def downgrade():
    op.drop_table("resource_reservations")
