"""Original explicit rebooking links and separate cancellations."""
from alembic import op, context
import sqlalchemy as sa

revision = "8af04d719b32"
down_revision = "72c18fba901d"
branch_labels = None
depends_on = None


def provenance():
    return [sa.Column("reason", sa.String(240), nullable=False), sa.Column("actor_id", sa.String(160), nullable=False),
            sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("employee_rebookings",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False), sa.Column("session_id", sa.String(80), nullable=True),
        sa.Column("source_appointment_id", sa.String(80), nullable=True), sa.Column("target_appointment_id", sa.String(80), nullable=False),
        sa.Column("source_capture", sa.JSON(), nullable=False), sa.Column("booking_capture", sa.JSON(), nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_rebooking_employee_owner"),
        sa.ForeignKeyConstraint(["institute_id", "session_id"], ["service_sessions.institute_id", "service_sessions.id"], name="fk_rebooking_session_owner"),
        sa.ForeignKeyConstraint(["institute_id", "source_appointment_id"], ["appointments.institute_id", "appointments.id"], name="fk_rebooking_source_booking_owner"),
        sa.ForeignKeyConstraint(["institute_id", "target_appointment_id"], ["appointments.institute_id", "appointments.id"], name="fk_rebooking_target_owner"),
        sa.UniqueConstraint("institute_id", "id", name="uq_rebooking_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_rebooking_replay"),
        sa.CheckConstraint("(session_id IS NOT NULL AND source_appointment_id IS NULL) OR (session_id IS NULL AND source_appointment_id IS NOT NULL)", name="ck_rebooking_one_source"),
        sa.CheckConstraint("source_appointment_id IS NULL OR source_appointment_id <> target_appointment_id", name="ck_rebooking_no_self"))
    op.create_index("ix_rebooking_employee_recorded", "employee_rebookings", ["institute_id", "employee_id", "created_at", "id"])
    op.create_table("rebooking_cancellations",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("rebooking_id", sa.String(80), nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "rebooking_id"], ["employee_rebookings.institute_id", "employee_rebookings.id"], name="fk_rebooking_cancel_owner"),
        sa.UniqueConstraint("institute_id", "rebooking_id", name="uq_rebooking_cancel_original"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_rebooking_cancel_replay"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Rebooking history verification requires an online downgrade")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
           for table in ("employee_rebookings", "rebooking_cancellations")):
        raise RuntimeError("Recorded rebooking history cannot be removed by downgrade")
    op.drop_table("rebooking_cancellations")
    op.drop_index("ix_rebooking_employee_recorded", table_name="employee_rebookings")
    op.drop_table("employee_rebookings")
