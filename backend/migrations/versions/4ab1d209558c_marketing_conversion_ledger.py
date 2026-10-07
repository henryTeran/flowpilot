"""Owned explicit conversion attribution originals and ticket heads."""
from alembic import context, op
import sqlalchemy as sa
revision = "4ab1d209558c"
down_revision = "3fa0c198447b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("marketing_conversion_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("ticket_id", sa.String(80), nullable=False),
        sa.Column("campaign_id", sa.String(80), nullable=False),
        sa.Column("intent_id", sa.String(80), nullable=False),
        sa.Column("authorization_id", sa.String(80), nullable=False),
        sa.Column("accepted_outcome_id", sa.String(80), nullable=False),
        sa.Column("previous_id", sa.String(80), nullable=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request", sa.JSON, nullable=False),
        sa.Column("attribution", sa.JSON, nullable=False),
        sa.Column("attribution_fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "ticket_id", "id", name="uq_marketing_conversion_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_marketing_conversion_replay"),
        sa.ForeignKeyConstraint(["institute_id", "ticket_id"], ["queue_tickets.institute_id", "queue_tickets.id"], name="fk_marketing_conversion_ticket"),
        sa.ForeignKeyConstraint(["institute_id", "intent_id"], ["marketing_dispatch_intents.institute_id", "marketing_dispatch_intents.id"], name="fk_marketing_conversion_intent"),
        sa.ForeignKeyConstraint(["institute_id", "campaign_id", "authorization_id"], ["marketing_campaign_originals.institute_id", "marketing_campaign_originals.campaign_id", "marketing_campaign_originals.id"], name="fk_marketing_conversion_send"),
        sa.ForeignKeyConstraint(["institute_id", "intent_id", "accepted_outcome_id"], ["marketing_dispatch_outcomes.institute_id", "marketing_dispatch_outcomes.intent_id", "marketing_dispatch_outcomes.id"], name="fk_marketing_conversion_outcome"),
        sa.ForeignKeyConstraint(["institute_id", "ticket_id", "previous_id"], ["marketing_conversion_originals.institute_id", "marketing_conversion_originals.ticket_id", "marketing_conversion_originals.id"], name="fk_marketing_conversion_previous"),
        sa.CheckConstraint("previous_id IS NULL OR previous_id <> id", name="ck_marketing_conversion_previous_distinct"),
        sa.CheckConstraint("action IN ('linked', 'retracted')", name="ck_marketing_conversion_action"),
        sa.CheckConstraint("action <> 'retracted' OR previous_id IS NOT NULL", name="ck_marketing_conversion_retraction_previous"))
    op.create_table("marketing_conversion_heads",
        sa.Column("institute_id", sa.String(80), primary_key=True),
        sa.Column("ticket_id", sa.String(80), primary_key=True),
        sa.Column("original_id", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "ticket_id", "original_id"],
            ["marketing_conversion_originals.institute_id", "marketing_conversion_originals.ticket_id", "marketing_conversion_originals.id"], name="fk_marketing_conversion_head"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Marketing conversion history verification requires online downgrade")
    tables = ("marketing_conversion_heads", "marketing_conversion_originals")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables):
        raise RuntimeError("Recorded marketing conversion history cannot be removed by downgrade")
    for table in tables: op.drop_table(table)
