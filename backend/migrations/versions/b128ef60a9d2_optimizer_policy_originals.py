"""Retain explicit optimizer weights and normalization assumptions.

Revision ID: b128ef60a9d2
Revises: a017d865bb4c
"""
from alembic import op, context
import sqlalchemy as sa
revision = "b128ef60a9d2"
down_revision = "a017d865bb4c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("optimizer_policy_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_optimizer_policy_replay"))
    op.create_index("ix_optimizer_policy_history", "optimizer_policy_originals", ["institute_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Optimizer policy verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM optimizer_policy_originals")).scalar():
        raise RuntimeError("Retained optimizer policies cannot be removed by downgrade")
    op.drop_index("ix_optimizer_policy_history", table_name="optimizer_policy_originals")
    op.drop_table("optimizer_policy_originals")
