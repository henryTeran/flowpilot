"""Owned dispatch intents and retained outcome originals."""
from alembic import context, op
import sqlalchemy as sa
revision = "3fa0c198447b"
down_revision = "2e9fb087336a"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("marketing_dispatch_intents",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("campaign_id", sa.String(80), nullable=False),
        sa.Column("approval_id", sa.String(80), nullable=False),
        sa.Column("customer_id", sa.String(80), nullable=False),
        sa.Column("contact_id", sa.String(80), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("submission", sa.JSON, nullable=False),
        sa.UniqueConstraint("institute_id", "id", name="uq_marketing_dispatch_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_marketing_dispatch_replay"),
        sa.UniqueConstraint("institute_id", "approval_id", "customer_id", name="uq_marketing_dispatch_recipient"),
        sa.ForeignKeyConstraint(["institute_id", "campaign_id", "approval_id"], ["marketing_campaign_originals.institute_id", "marketing_campaign_originals.campaign_id", "marketing_campaign_originals.id"], name="fk_marketing_dispatch_approval"),
        sa.ForeignKeyConstraint(["institute_id", "customer_id", "contact_id"], ["marketing_contact_originals.institute_id", "marketing_contact_originals.customer_id", "marketing_contact_originals.id"], name="fk_marketing_dispatch_contact"))
    op.create_table("marketing_dispatch_outcomes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("intent_id", sa.String(80), nullable=False),
        sa.Column("previous_id", sa.String(80), nullable=True),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.JSON, nullable=False),
        sa.UniqueConstraint("institute_id", "intent_id", "id", name="uq_marketing_outcome_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_marketing_outcome_replay"),
        sa.ForeignKeyConstraint(["institute_id", "intent_id"], ["marketing_dispatch_intents.institute_id", "marketing_dispatch_intents.id"], name="fk_marketing_outcome_intent"),
        sa.ForeignKeyConstraint(["institute_id", "intent_id", "previous_id"], ["marketing_dispatch_outcomes.institute_id", "marketing_dispatch_outcomes.intent_id", "marketing_dispatch_outcomes.id"], name="fk_marketing_outcome_previous"),
        sa.CheckConstraint("previous_id IS NULL OR previous_id <> id", name="ck_marketing_outcome_previous_distinct"))
    op.create_table("marketing_dispatch_heads",
        sa.Column("institute_id", sa.String(80), primary_key=True),
        sa.Column("intent_id", sa.String(80), primary_key=True),
        sa.Column("original_id", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "intent_id", "original_id"], ["marketing_dispatch_outcomes.institute_id", "marketing_dispatch_outcomes.intent_id", "marketing_dispatch_outcomes.id"], name="fk_marketing_dispatch_head"))

def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Marketing dispatch history verification requires online downgrade")
    tables = ("marketing_dispatch_heads", "marketing_dispatch_outcomes", "marketing_dispatch_intents")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables):
        raise RuntimeError("Recorded marketing dispatch history cannot be removed by downgrade")
    for table in tables: op.drop_table(table)
