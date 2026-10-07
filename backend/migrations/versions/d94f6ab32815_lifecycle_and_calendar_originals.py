"""Customer lifecycle declarations and institution birthday calendar originals."""
from alembic import context, op
import sqlalchemy as sa
revision = "d94f6ab32815"
down_revision = "c83e5fa21704"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("crm_birthday_policy_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("previous_policy_id", sa.String(80), nullable=True),
        sa.Column("policy", sa.JSON, nullable=False), sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False), sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("institute_id", "id", name="uq_crm_birthday_policy_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_crm_birthday_policy_replay"),
        sa.ForeignKeyConstraint(["institute_id", "previous_policy_id"],
            ["crm_birthday_policy_originals.institute_id", "crm_birthday_policy_originals.id"], name="fk_crm_birthday_policy_previous_owner"))
    op.create_table("crm_birthday_policy_heads",
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), primary_key=True),
        sa.Column("policy_id", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "policy_id"],
            ["crm_birthday_policy_originals.institute_id", "crm_birthday_policy_originals.id"], name="fk_crm_birthday_policy_head_owner"))
    op.create_table("crm_lifecycle_originals",
        sa.Column("id",sa.String(80),primary_key=True),
        sa.Column("institute_id",sa.String(80),sa.ForeignKey("institutes.id"),nullable=False),
        sa.Column("customer_id",sa.String(80),sa.ForeignKey("customers.id"),nullable=False),
        sa.Column("previous_id",sa.String(80),nullable=True),
        sa.Column("declaration",sa.JSON,nullable=False),sa.Column("reason",sa.String(240),nullable=False),
        sa.Column("actor_id",sa.String(160),nullable=False),sa.Column("idempotency_key",sa.String(120),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("institute_id","customer_id","id",name="uq_crm_lifecycle_owner"),
        sa.UniqueConstraint("institute_id","customer_id","idempotency_key",name="uq_crm_lifecycle_replay"),
        sa.ForeignKeyConstraint(["institute_id","customer_id","previous_id"],
            ["crm_lifecycle_originals.institute_id","crm_lifecycle_originals.customer_id","crm_lifecycle_originals.id"],name="fk_crm_lifecycle_previous_owner"))
    op.create_table("crm_lifecycle_heads",
        sa.Column("institute_id",sa.String(80),sa.ForeignKey("institutes.id"),primary_key=True),
        sa.Column("customer_id",sa.String(80),sa.ForeignKey("customers.id"),primary_key=True),
        sa.Column("original_id",sa.String(80),nullable=False),
        sa.ForeignKeyConstraint(["institute_id","customer_id","original_id"],
            ["crm_lifecycle_originals.institute_id","crm_lifecycle_originals.customer_id","crm_lifecycle_originals.id"],name="fk_crm_lifecycle_head_owner"))

def downgrade():
    if context.is_offline_mode(): raise RuntimeError("Lifecycle history verification requires an online downgrade")
    tables = ("crm_lifecycle_heads", "crm_lifecycle_originals", "crm_birthday_policy_heads", "crm_birthday_policy_originals")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables):
        raise RuntimeError("Recorded lifecycle/calendar history cannot be removed by downgrade")
    for table in tables: op.drop_table(table)
