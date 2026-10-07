"""Owned marketing contact declarations and current pointers."""
from alembic import context, op
import sqlalchemy as sa

revision = "2e9fb087336a"
down_revision = "1d8eaf762259"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("marketing_contact_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("customer_id", sa.String(80), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("previous_id", sa.String(80), nullable=True),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("declaration", sa.JSON, nullable=False),
        sa.UniqueConstraint("institute_id", "customer_id", "id", name="uq_marketing_contact_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_marketing_contact_replay"),
        sa.ForeignKeyConstraint(["institute_id", "customer_id", "previous_id"],
            ["marketing_contact_originals.institute_id", "marketing_contact_originals.customer_id", "marketing_contact_originals.id"],
            name="fk_marketing_contact_previous_owner"),
        sa.CheckConstraint("previous_id IS NULL OR previous_id <> id", name="ck_marketing_contact_previous_distinct"))
    op.create_table("marketing_contact_heads",
        sa.Column("institute_id", sa.String(80), primary_key=True),
        sa.Column("customer_id", sa.String(80), primary_key=True),
        sa.Column("original_id", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "customer_id", "original_id"],
            ["marketing_contact_originals.institute_id", "marketing_contact_originals.customer_id", "marketing_contact_originals.id"],
            name="fk_marketing_contact_head_owner"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Marketing contact history verification requires online downgrade")
    tables = ("marketing_contact_heads", "marketing_contact_originals")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables):
        raise RuntimeError("Recorded marketing contact history cannot be removed by downgrade")
    for table in tables:
        op.drop_table(table)
