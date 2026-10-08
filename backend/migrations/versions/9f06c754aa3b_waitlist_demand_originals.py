"""Retain explicit waitlist demand declarations.

Revision ID: 9f06c754aa3b
Revises: 8ef5b643992a
"""
from alembic import op, context
import sqlalchemy as sa

revision = "9f06c754aa3b"
down_revision = "8ef5b643992a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("waitlist_demand_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("customer_id", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_waitlist_demand_replay"))
    op.create_index("ix_waitlist_demand_history", "waitlist_demand_originals", ["institute_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Waitlist demand verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM waitlist_demand_originals")).scalar():
        raise RuntimeError("Retained waitlist demands cannot be removed by downgrade")
    op.drop_index("ix_waitlist_demand_history", table_name="waitlist_demand_originals")
    op.drop_table("waitlist_demand_originals")
