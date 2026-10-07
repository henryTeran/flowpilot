"""Original signed absence/leave intervals and immutable cancellations."""
from alembic import op, context
import sqlalchemy as sa

revision = "3da908e5f70c"
down_revision = "2c897df4e6fb"
branch_labels = None
depends_on = None


def provenance():
    return [sa.Column("reason", sa.String(240), nullable=False), sa.Column("actor_id", sa.String(160), nullable=False),
            sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_index("uq_employee_owner", "employees", ["institute_id", "id"], unique=True)
    op.create_table("employee_absences",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False), sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False), sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_absence_employee_owner"),
        sa.UniqueConstraint("institute_id", "id", name="uq_absence_owner"), sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_absence_replay"),
        sa.CheckConstraint("kind IN ('absence','leave')", name="ck_absence_kind"), sa.CheckConstraint("end_time > start_time", name="ck_absence_interval"))
    op.create_index("ix_absence_employee_slot", "employee_absences", ["institute_id", "employee_id", "start_time", "end_time"])
    op.create_table("absence_cancellations",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("absence_id", sa.String(80), nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "absence_id"], ["employee_absences.institute_id", "employee_absences.id"], name="fk_absence_cancel_owner"),
        sa.UniqueConstraint("institute_id", "absence_id", name="uq_absence_cancel_original"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_absence_cancel_replay"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Workforce history verification requires an online downgrade")
    bind = op.get_bind()
    if any(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in ("employee_absences", "absence_cancellations")):
        raise RuntimeError("Recorded workforce history cannot be removed by downgrade")
    op.drop_table("absence_cancellations")
    op.drop_index("ix_absence_employee_slot", table_name="employee_absences")
    op.drop_table("employee_absences")
    op.drop_index("uq_employee_owner", table_name="employees")
