"""Atomically retain scoped approved execution and existing booking-event proof."""
from alembic import op, context
import sqlalchemy as sa
revision = "f562c3a4edf6"
down_revision = "e451b293dcf5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("base_execution_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("operation_id", sa.String(80), sa.ForeignKey("base_sensitive_operation_originals.id"), nullable=False),
        sa.Column("approval_id", sa.String(80), sa.ForeignKey("base_approval_originals.id"), nullable=False),
        sa.Column("booking_event_id", sa.String(80), sa.ForeignKey("booking_events.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_base_execution_replay"),
        sa.UniqueConstraint("operation_id", name="uq_base_execution_operation"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("BASE execution verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM base_execution_originals")).scalar():
        raise RuntimeError("Retained BASE executions cannot be removed by downgrade")
    op.drop_table("base_execution_originals")
