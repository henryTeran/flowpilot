"""Retained reorder proposals, without purchase authority."""
from alembic import op, context
import sqlalchemy as sa
revision = "1784e5c6a1b8"
down_revision = "0673d4b5f0a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stock_reorder_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_reorder_replay"))
    op.create_index("ix_stock_reorder_history", "stock_reorder_originals", ["institute_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():raise RuntimeError("Reorder original verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM stock_reorder_originals")).scalar():
        raise RuntimeError("Retained reorder proposals cannot be removed by downgrade")
    op.drop_index("ix_stock_reorder_history", table_name="stock_reorder_originals")
    op.drop_table("stock_reorder_originals")
