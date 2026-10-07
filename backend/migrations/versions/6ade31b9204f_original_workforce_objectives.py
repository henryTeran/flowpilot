"""Original workforce objectives and separate signed cancellations."""
from alembic import op, context
import sqlalchemy as sa

revision = "6ade31b9204f"
down_revision = "5fcb2a07193e"
branch_labels = None
depends_on = None


def provenance():
    return [sa.Column("reason", sa.String(240), nullable=False), sa.Column("actor_id", sa.String(160), nullable=False),
            sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("employee_objectives",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False), sa.Column("title", sa.String(120), nullable=False),
        sa.Column("metric", sa.String(40), nullable=False), sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("target", sa.String(32), nullable=False), sa.Column("first_day", sa.Date, nullable=False),
        sa.Column("last_day", sa.Date, nullable=False), sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False), sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_objective_employee_owner"),
        sa.UniqueConstraint("institute_id", "id", name="uq_objective_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_objective_replay"),
        sa.CheckConstraint("CAST(target AS NUMERIC) > 0 AND period_end > period_start AND last_day >= first_day", name="ck_objective_period_target"),
        sa.CheckConstraint("(metric = 'closed_attributed_gross' AND currency IS NOT NULL AND currency IN ('CHF', 'EUR')) OR (metric = 'completed_sessions' AND currency IS NULL AND CAST(target AS NUMERIC) = CAST(CAST(target AS NUMERIC) AS BIGINT))", name="ck_objective_metric_unit"))
    op.create_index("ix_objective_employee_period", "employee_objectives", ["institute_id", "employee_id", "period_start", "period_end"])
    op.create_table("objective_cancellations",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("objective_id", sa.String(80), nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "objective_id"], ["employee_objectives.institute_id", "employee_objectives.id"], name="fk_objective_cancel_owner"),
        sa.UniqueConstraint("institute_id", "objective_id", name="uq_objective_cancelled_original"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_objective_cancel_replay"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Objective history verification requires an online downgrade")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
           for table in ("employee_objectives", "objective_cancellations")):
        raise RuntimeError("Recorded objective history cannot be removed by downgrade")
    op.drop_table("objective_cancellations")
    op.drop_index("ix_objective_employee_period", table_name="employee_objectives")
    op.drop_table("employee_objectives")
