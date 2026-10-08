"""Retain explicit closure-rate decisions and selected historical evidence.

Revision ID: 8ef5b643992a
Revises: 7de4a532881f
"""
from alembic import op, context
import sqlalchemy as sa

revision = "8ef5b643992a"
down_revision = "7de4a532881f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("revenue_closure_valuation_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("appointment_id", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_revenue_closure_valuation_replay"))
    op.create_index("ix_revenue_closure_valuation_history", "revenue_closure_valuation_originals", ["institute_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Closure valuation verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM revenue_closure_valuation_originals")).scalar():
        raise RuntimeError("Retained closure valuations cannot be removed by downgrade")
    op.drop_index("ix_revenue_closure_valuation_history", table_name="revenue_closure_valuation_originals")
    op.drop_table("revenue_closure_valuation_originals")
