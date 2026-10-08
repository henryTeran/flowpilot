"""Retain pending sensitive BASE operations without approval or execution."""
from alembic import op, context
import sqlalchemy as sa
revision = "d340a182cbe4"
down_revision = "c239f071bad3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("base_sensitive_operation_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_base_sensitive_operation_replay"))
    op.create_index("ix_base_sensitive_operation_history", "base_sensitive_operation_originals", ["institute_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Sensitive BASE operation verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM base_sensitive_operation_originals")).scalar():
        raise RuntimeError("Retained sensitive BASE operations cannot be removed by downgrade")
    op.drop_index("ix_base_sensitive_operation_history", table_name="base_sensitive_operation_originals")
    op.drop_table("base_sensitive_operation_originals")
