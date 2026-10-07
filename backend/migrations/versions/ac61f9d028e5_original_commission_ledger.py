"""Original source-linked commissions and separate cancellations."""
from alembic import op, context
import sqlalchemy as sa

revision = "ac61f9d028e5"
down_revision = "9bc52e18d430"
branch_labels = None
depends_on = None


def provenance():
    return [sa.Column("reason", sa.String(240), nullable=False), sa.Column("actor_id", sa.String(160), nullable=False),
            sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("employee_commissions",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False), sa.Column("rule_id", sa.String(80), nullable=False),
        sa.Column("ticket_id", sa.String(80), nullable=False), sa.Column("line_id", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("amount_minor", sa.String(30), nullable=False),
        sa.Column("rule_capture", sa.JSON, nullable=False), sa.Column("calculation", sa.JSON, nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_commission_employee_owner"),
        sa.ForeignKeyConstraint(["institute_id", "rule_id"], ["employee_commission_rules.institute_id", "employee_commission_rules.id"], name="fk_commission_rule_owner"),
        sa.ForeignKeyConstraint(["institute_id", "ticket_id"], ["queue_tickets.institute_id", "queue_tickets.id"], name="fk_commission_ticket_owner"),
        sa.ForeignKeyConstraint(["ticket_id", "line_id"], ["ticket_lines.ticket_id", "ticket_lines.id"], name="fk_commission_line_owner"),
        sa.UniqueConstraint("institute_id", "id", name="uq_commission_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_commission_replay"),
        sa.CheckConstraint("currency IN ('CHF', 'EUR') AND length(amount_minor) BETWEEN 1 AND 10 AND CAST(amount_minor AS BIGINT) >= 0 AND amount_minor = CAST(CAST(amount_minor AS BIGINT) AS VARCHAR)", name="ck_commission_money"))
    op.create_index("ix_commission_employee_recorded", "employee_commissions", ["institute_id", "employee_id", "created_at", "id"])
    op.create_index("ix_commission_source", "employee_commissions", ["institute_id", "line_id"])
    op.create_table("commission_cancellations",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("commission_id", sa.String(80), nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "commission_id"], ["employee_commissions.institute_id", "employee_commissions.id"], name="fk_commission_cancel_owner"),
        sa.UniqueConstraint("institute_id", "commission_id", name="uq_commission_cancel_original"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_commission_cancel_replay"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Commission history verification requires an online downgrade")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        for table in ("employee_commissions", "commission_cancellations")):
        raise RuntimeError("Recorded commission history cannot be removed by downgrade")
    op.drop_table("commission_cancellations")
    op.drop_index("ix_commission_source", table_name="employee_commissions")
    op.drop_index("ix_commission_employee_recorded", table_name="employee_commissions")
    op.drop_table("employee_commissions")
