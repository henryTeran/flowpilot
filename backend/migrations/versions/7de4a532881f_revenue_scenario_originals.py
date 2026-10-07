"""Retain explicit recorded-gross scenarios and their original evidence.

Revision ID: 7de4a532881f
Revises: 6cd3f421770e
"""
from alembic import op, context
import sqlalchemy as sa

revision = "7de4a532881f"
down_revision = "6cd3f421770e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("revenue_scenario_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_revenue_scenario_replay"))
    op.create_index("ix_revenue_scenario_history", "revenue_scenario_originals", ["institute_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Scenario original verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM revenue_scenario_originals")).scalar():
        raise RuntimeError("Retained scenario originals cannot be removed by downgrade")
    op.drop_index("ix_revenue_scenario_history", table_name="revenue_scenario_originals")
    op.drop_table("revenue_scenario_originals")
