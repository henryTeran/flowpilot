"""Captured checkout application facts."""
from alembic import op
import sqlalchemy as sa
revision = "60cd01587bdf"
down_revision = "5fbc90476acf"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_capture_applications",
        sa.Column("ticket_id", sa.String(80), sa.ForeignKey("queue_tickets.id"), primary_key=True),
        sa.Column("intent_id", sa.String(80), sa.ForeignKey("payment_parent_executions.intent_id"), nullable=False, unique=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("employee_id", sa.String(80), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_payment_capture_applications_institute_id", "payment_capture_applications", ["institute_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT ticket_id FROM payment_capture_applications LIMIT 1")).first():
        raise RuntimeError("Capture applications exist; downgrade cannot preserve settlement application")
    op.drop_table("payment_capture_applications")
