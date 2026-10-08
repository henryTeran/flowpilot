"""Retain explicit waitlist activation/revision/cancellation.

Revision ID: a017d865bb4c
Revises: 9f06c754aa3b
"""
from alembic import op, context
import sqlalchemy as sa

revision = "a017d865bb4c"
down_revision = "9f06c754aa3b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("waitlist_lifecycle_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("root_id", sa.String(80), nullable=False),
        sa.Column("previous_id", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_waitlist_lifecycle_replay"),
        sa.UniqueConstraint("institute_id", "root_id", "previous_id", name="uq_waitlist_lifecycle_successor"))
    op.create_index("ix_waitlist_lifecycle_history", "waitlist_lifecycle_originals", ["institute_id", "root_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Waitlist lifecycle verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM waitlist_lifecycle_originals")).scalar():
        raise RuntimeError("Retained waitlist lifecycle cannot be removed by downgrade")
    op.drop_index("ix_waitlist_lifecycle_history", table_name="waitlist_lifecycle_originals")
    op.drop_table("waitlist_lifecycle_originals")
