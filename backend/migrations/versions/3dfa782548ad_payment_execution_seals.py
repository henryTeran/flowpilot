"""Durable authorization execution seals."""
from alembic import op
import sqlalchemy as sa
revision = "3dfa782548ad"
down_revision = "2cef6714379c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_executions",
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_intents.id"), primary_key=True),
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), nullable=False),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))
    for column in ("ticket_id", "institute_id"):
        op.create_index("ix_payment_executions_" + column, "payment_executions", [column])
    op.create_index("uq_payment_execution_active_ticket", "payment_executions", ["ticket_id"],
                    unique=True, sqlite_where=sa.text("released_at IS NULL"),
                    postgresql_where=sa.text("released_at IS NULL"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT intent_id FROM payment_executions LIMIT 1")).first():
        raise RuntimeError("Payment executions exist; downgrade cannot preserve execution seals")
    op.drop_table("payment_executions")
