"""Institute-scoped package plans, entitlements and checkout consumption."""
from alembic import op
import sqlalchemy as sa

revision = "b9d234a764cf"
down_revision = "a8c123f653be"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("package_plans",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("service_id", sa.String(80), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sessions", sa.Integer(), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False),
        sa.CheckConstraint("sessions > 0 AND valid_days > 0", name="ck_package_plan_terms"))
    op.create_index("ix_package_plans_institute_id", "package_plans", ["institute_id"])
    op.create_table("customer_packages",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("plan_id", sa.String(80), sa.ForeignKey("package_plans.id"), nullable=False),
        sa.Column("customer_id", sa.String(80), nullable=False),
        sa.Column("service_id", sa.String(80), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sessions", sa.Integer(), nullable=False),
        sa.Column("consumed", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=True),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_package_issue_replay"),
        sa.CheckConstraint("sessions > 0 AND consumed >= 0 AND consumed <= sessions", name="ck_package_balance"),
        sa.CheckConstraint("expires_at > issued_at", name="ck_package_expiry"))
    op.create_index("ix_customer_packages_institute_id", "customer_packages", ["institute_id"])
    op.create_index("ix_customer_packages_customer_id", "customer_packages", ["customer_id"])
    op.create_table("package_redemptions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("package_id", sa.String(80), sa.ForeignKey("customer_packages.id"), nullable=False),
        sa.Column("ticket_line_id", sa.String(80), sa.ForeignKey("ticket_lines.id"), nullable=False),
        sa.Column("sessions", sa.Integer(), nullable=False),
        sa.Column("original_unit_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("original_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=True),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_package_redeem_replay"),
        sa.UniqueConstraint("ticket_line_id", name="uq_package_redeem_line"),
        sa.CheckConstraint("sessions > 0", name="ck_package_redeem_sessions"))
    op.create_index("ix_package_redemptions_institute_id", "package_redemptions", ["institute_id"])
    op.create_index("ix_package_redemptions_package_id", "package_redemptions", ["package_id"])


def downgrade():
    op.drop_table("package_redemptions")
    op.drop_table("customer_packages")
    op.drop_table("package_plans")
