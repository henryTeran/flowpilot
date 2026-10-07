"""Original workforce commission rules and separate signed cancellations."""
from alembic import op, context
import sqlalchemy as sa

revision = "9bc52e18d430"
down_revision = "8af04d719b32"
branch_labels = None
depends_on = None


def provenance():
    return [sa.Column("reason", sa.String(240), nullable=False), sa.Column("actor_id", sa.String(160), nullable=False),
            sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("employee_commission_rules",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False), sa.Column("title", sa.String(120), nullable=False),
        sa.Column("basis", sa.String(40), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("category", sa.String(40), nullable=False), sa.Column("service_id", sa.String(80), sa.ForeignKey("services.id"), nullable=True),
        sa.Column("rounding", sa.String(16), nullable=False), sa.Column("rate_basis_points", sa.Integer, nullable=False), sa.Column("first_day", sa.Date, nullable=False),
        sa.Column("last_day", sa.Date, nullable=False), sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False), sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_commission_rule_employee_owner"),
        sa.UniqueConstraint("institute_id", "id", name="uq_commission_rule_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_commission_rule_replay"),
        sa.CheckConstraint("rate_basis_points >= 0 AND rate_basis_points <= 10000 AND rate_basis_points = CAST(rate_basis_points AS INTEGER) AND period_end > period_start AND last_day >= first_day", name="ck_commission_rule_period_rate"),
        sa.CheckConstraint("basis = 'closed_attributed_line_gross' AND currency IN ('CHF', 'EUR') AND rounding IN ('half_up', 'half_even', 'down') AND length(trim(category)) > 0", name="ck_commission_rule_terms"))
    op.create_index("ix_commission_rule_employee_period", "employee_commission_rules", ["institute_id", "employee_id", "period_start", "period_end"])
    op.create_table("commission_rule_cancellations",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("rule_id", sa.String(80), nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "rule_id"], ["employee_commission_rules.institute_id", "employee_commission_rules.id"], name="fk_commission_rule_cancel_owner"),
        sa.UniqueConstraint("institute_id", "rule_id", name="uq_commission_rule_cancelled_original"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_commission_rule_cancel_replay"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Commission rule history verification requires an online downgrade")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
           for table in ("employee_commission_rules", "commission_rule_cancellations")):
        raise RuntimeError("Recorded commission rule history cannot be removed by downgrade")
    op.drop_table("commission_rule_cancellations")
    op.drop_index("ix_commission_rule_employee_period", table_name="employee_commission_rules")
    op.drop_table("employee_commission_rules")
