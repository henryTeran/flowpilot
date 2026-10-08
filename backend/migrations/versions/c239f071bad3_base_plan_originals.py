"""Retain BASE read/suggest preparations, not execution approvals."""
from alembic import op, context
import sqlalchemy as sa
revision = "c239f071bad3"
down_revision = "b128ef60a9d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("base_plan_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_base_plan_replay"))
    op.create_index("ix_base_plan_history", "base_plan_originals", ["institute_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("BASE plan verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM base_plan_originals")).scalar():
        raise RuntimeError("Retained BASE preparations cannot be removed by downgrade")
    op.drop_index("ix_base_plan_history", table_name="base_plan_originals")
    op.drop_table("base_plan_originals")
