"""Minimal scoped customer identity for commercial beneficiary selection."""
from alembic import op
import sqlalchemy as sa

revision = "d1f456c986e1"
down_revision = "c0e345b875d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("customers",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("search_name", sa.String(4096), nullable=False),
        sa.Column("phone_digits", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("creation_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=True),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_customer_creation_replay"))
    op.create_index("ix_customers_institute_id", "customers", ["institute_id"])
    op.add_column("appointments", sa.Column("customer_id", sa.String(80), nullable=True))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT id FROM customers LIMIT 1")).first() is not None:
        raise RuntimeError("Customer identity records exist; downgrade cannot preserve them")
    with op.batch_alter_table("appointments") as batch:
        batch.drop_column("customer_id")
    op.drop_table("customers")
