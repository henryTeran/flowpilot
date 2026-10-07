"""Original declared effective work intervals and separate cancellations."""
from alembic import op, context
import sqlalchemy as sa

revision = "72c18fba901d"
down_revision = "6ade31b9204f"
branch_labels = None
depends_on = None


def provenance():
    return [sa.Column("reason", sa.String(240), nullable=False), sa.Column("actor_id", sa.String(160), nullable=False),
            sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("employee_work_intervals",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False), sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_work_interval_employee_owner"),
        sa.UniqueConstraint("institute_id", "id", name="uq_work_interval_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_work_interval_replay"),
        sa.CheckConstraint("end_time > start_time", name="ck_work_interval_positive"))
    op.create_index("ix_work_interval_employee_time", "employee_work_intervals", ["institute_id", "employee_id", "start_time", "end_time"])
    op.create_table("work_interval_cancellations",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("work_interval_id", sa.String(80), nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "work_interval_id"], ["employee_work_intervals.institute_id", "employee_work_intervals.id"], name="fk_work_interval_cancel_owner"),
        sa.UniqueConstraint("institute_id", "work_interval_id", name="uq_work_interval_cancelled_original"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_work_interval_cancel_replay"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Work interval history verification requires an online downgrade")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
           for table in ("employee_work_intervals", "work_interval_cancellations")):
        raise RuntimeError("Recorded work interval history cannot be removed by downgrade")
    op.drop_table("work_interval_cancellations")
    op.drop_index("ix_work_interval_employee_time", table_name="employee_work_intervals")
    op.drop_table("employee_work_intervals")
