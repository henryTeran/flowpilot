"""Durable, replay-safe service extensions.

Revision ID: 8a4d71f0b2c9
Revises: 6f8c2d1a930b
"""
from alembic import op
import sqlalchemy as sa

revision = "8a4d71f0b2c9"
down_revision = "6f8c2d1a930b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "session_extensions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("session_id", sa.String(80), sa.ForeignKey("service_sessions.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("previous_end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resulting_end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by", sa.String(160), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_session_extension_replay"),
        sa.CheckConstraint("minutes IN (5, 10, 15, 20, 30, 45, 60)", name="ck_session_extension_minutes"),
    )
    op.create_index("ix_session_extensions_institute_id", "session_extensions", ["institute_id"])
    op.create_index("ix_session_extensions_session_id", "session_extensions", ["session_id"])


def downgrade():
    op.drop_table("session_extensions")
