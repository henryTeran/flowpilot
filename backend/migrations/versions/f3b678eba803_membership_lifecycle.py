"""Membership terms and immutable renewal history, without payment settlement."""
from alembic import op
import sqlalchemy as sa

revision = "f3b678eba803"
down_revision = "e2a567da97f2"
branch_labels = None
depends_on = None


def scope_columns():
    return [sa.Column("id", sa.String(80), primary_key=True),
            sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
            sa.Column("idempotency_key", sa.String(120), nullable=False),
            sa.Column("actor_id", sa.String(160), nullable=True)]


def date_column(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False)


def upgrade():
    op.create_table("membership_plans", *scope_columns(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False),
        sa.Column("creation_fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_membership_plan_replay"),
        sa.CheckConstraint("valid_days > 0", name="ck_membership_plan_days"))
    op.create_index("ix_membership_plans_institute_id", "membership_plans", ["institute_id"])
    op.create_table("customer_memberships", *scope_columns(),
        sa.Column("plan_id", sa.String(80), sa.ForeignKey("membership_plans.id"), nullable=False),
        sa.Column("customer_id", sa.String(80), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False),
        date_column("issued_at"), date_column("active_from"), date_column("active_until"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_membership_issue_replay"),
        sa.CheckConstraint("valid_days > 0 AND active_until > active_from AND active_from >= issued_at", name="ck_membership_term"))
    op.create_index("ix_customer_memberships_institute_id", "customer_memberships", ["institute_id"])
    op.create_index("ix_customer_memberships_customer_id", "customer_memberships", ["customer_id"])
    op.create_table("membership_renewals", *scope_columns(),
        sa.Column("membership_id", sa.String(80), sa.ForeignKey("customer_memberships.id"), nullable=False),
        *[date_column(name) for name in ("previous_from", "previous_until", "active_from", "active_until", "occurred_at")],
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_membership_renewal_replay"),
        sa.CheckConstraint("previous_until > previous_from AND active_until > active_from AND "
            "active_until > previous_until AND active_from >= previous_from AND occurred_at >= previous_from",
            name="ck_membership_renewal_term"))
    op.create_index("ix_membership_renewals_institute_id", "membership_renewals", ["institute_id"])
    op.create_index("ix_membership_renewals_membership_id", "membership_renewals", ["membership_id"])


def downgrade():
    for table in ("membership_plans", "customer_memberships", "membership_renewals"):
        if op.get_bind().execute(sa.text(f"SELECT id FROM {table} LIMIT 1")).first():
            raise RuntimeError("Membership records exist; downgrade cannot preserve entitlement/history")
    op.drop_table("membership_renewals")
    op.drop_table("customer_memberships")
    op.drop_table("membership_plans")
