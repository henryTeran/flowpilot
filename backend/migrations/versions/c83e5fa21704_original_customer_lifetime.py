"""Scoped customer lifetime assumption originals and current pointers."""
from alembic import context, op
import sqlalchemy as sa

revision = "c83e5fa21704"
down_revision = "b72d4e91a603"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("crm_lifetime_originals",
        sa.Column("id",sa.String(80),primary_key=True),
        sa.Column("institute_id",sa.String(80),sa.ForeignKey("institutes.id"),nullable=False),
        sa.Column("customer_id",sa.String(80),sa.ForeignKey("customers.id"),nullable=False),
        sa.Column("previous_id",sa.String(80),nullable=True),
        sa.Column("assumptions",sa.JSON,nullable=False),sa.Column("reason",sa.String(240),nullable=False),
        sa.Column("actor_id",sa.String(160),nullable=False),sa.Column("idempotency_key",sa.String(120),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("institute_id","customer_id","id",name="uq_crm_lifetime_owner"),
        sa.UniqueConstraint("institute_id","customer_id","idempotency_key",name="uq_crm_lifetime_replay"),
        sa.ForeignKeyConstraint(["institute_id","customer_id","previous_id"],
            ["crm_lifetime_originals.institute_id","crm_lifetime_originals.customer_id","crm_lifetime_originals.id"],name="fk_crm_lifetime_previous_owner"))
    op.create_table("crm_lifetime_heads",
        sa.Column("institute_id",sa.String(80),sa.ForeignKey("institutes.id"),primary_key=True),
        sa.Column("customer_id",sa.String(80),sa.ForeignKey("customers.id"),primary_key=True),
        sa.Column("original_id",sa.String(80),nullable=False),
        sa.ForeignKeyConstraint(["institute_id","customer_id","original_id"],
            ["crm_lifetime_originals.institute_id","crm_lifetime_originals.customer_id","crm_lifetime_originals.id"],name="fk_crm_lifetime_head_owner"))

def downgrade():
    if context.is_offline_mode(): raise RuntimeError("Lifetime history verification requires an online downgrade")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
           for table in ("crm_lifetime_heads","crm_lifetime_originals")):
        raise RuntimeError("Recorded lifetime history cannot be removed by downgrade")
    op.drop_table("crm_lifetime_heads")
    op.drop_table("crm_lifetime_originals")
