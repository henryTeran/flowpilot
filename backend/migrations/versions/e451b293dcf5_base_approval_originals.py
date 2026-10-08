"""Retain explicit causal approval decisions without execution."""
from alembic import op, context
import sqlalchemy as sa
revision = "e451b293dcf5"
down_revision = "d340a182cbe4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("base_approval_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("operation_id", sa.String(80), sa.ForeignKey("base_sensitive_operation_originals.id"), nullable=False),
        sa.Column("previous_id", sa.String(80), sa.ForeignKey("base_approval_originals.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_base_approval_replay"),
        sa.UniqueConstraint("operation_id", "previous_id", name="uq_base_approval_successor"))
    op.create_index("ix_base_approval_history", "base_approval_originals", ["institute_id", "operation_id", "created_at", "id"])


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("BASE approval verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM base_approval_originals")).scalar():
        raise RuntimeError("Retained BASE approvals cannot be removed by downgrade")
    op.drop_index("ix_base_approval_history", table_name="base_approval_originals")
    op.drop_table("base_approval_originals")
