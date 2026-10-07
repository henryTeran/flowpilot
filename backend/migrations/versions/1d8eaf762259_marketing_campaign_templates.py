"""Owned campaign/template revisions and selected heads."""
from alembic import context,op
import sqlalchemy as sa
revision="1d8eaf762259"
down_revision="0c7d9ef65148"
branch_labels=None
depends_on=None

def shared(kind):
    return [sa.Column("id",sa.String(80),primary_key=True),sa.Column("institute_id",sa.String(80),sa.ForeignKey("institutes.id"),nullable=False),sa.Column(kind+"_id",sa.String(80),nullable=False),sa.Column("previous_id",sa.String(80),nullable=True),sa.Column("actor_id",sa.String(160),nullable=False),sa.Column("reason",sa.String(240),nullable=False),sa.Column("idempotency_key",sa.String(120),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("request",sa.JSON,nullable=False)]
def upgrade():
    op.create_table("marketing_template_originals",*shared("template"),sa.Column("content",sa.JSON,nullable=False),
        sa.UniqueConstraint("institute_id","id",name="uq_marketing_template_owner"),sa.UniqueConstraint("institute_id","template_id","id",name="uq_marketing_template_revision"),sa.UniqueConstraint("institute_id","idempotency_key",name="uq_marketing_template_replay"),
        sa.ForeignKeyConstraint(["institute_id","template_id","previous_id"],["marketing_template_originals.institute_id","marketing_template_originals.template_id","marketing_template_originals.id"],name="fk_marketing_template_previous"))
    op.create_table("marketing_template_heads",sa.Column("institute_id",sa.String(80),primary_key=True),sa.Column("template_id",sa.String(80),primary_key=True),sa.Column("original_id",sa.String(80),nullable=False),sa.ForeignKeyConstraint(["institute_id","template_id","original_id"],["marketing_template_originals.institute_id","marketing_template_originals.template_id","marketing_template_originals.id"],name="fk_marketing_template_head"))
    op.create_table("marketing_campaign_originals",*shared("campaign"),sa.Column("audience_id",sa.String(80),nullable=False),sa.Column("template_original_id",sa.String(80),nullable=True),sa.Column("revision",sa.JSON,nullable=False),
        sa.UniqueConstraint("institute_id","campaign_id","id",name="uq_marketing_campaign_revision"),sa.UniqueConstraint("institute_id","idempotency_key",name="uq_marketing_campaign_replay"),
        sa.ForeignKeyConstraint(["institute_id","campaign_id","previous_id"],["marketing_campaign_originals.institute_id","marketing_campaign_originals.campaign_id","marketing_campaign_originals.id"],name="fk_marketing_campaign_previous"),
        sa.ForeignKeyConstraint(["institute_id","audience_id"],["marketing_audience_originals.institute_id","marketing_audience_originals.id"],name="fk_marketing_campaign_audience"),
        sa.ForeignKeyConstraint(["institute_id","template_original_id"],["marketing_template_originals.institute_id","marketing_template_originals.id"],name="fk_marketing_campaign_template"))
    op.create_table("marketing_campaign_heads",sa.Column("institute_id",sa.String(80),primary_key=True),sa.Column("campaign_id",sa.String(80),primary_key=True),sa.Column("original_id",sa.String(80),nullable=False),sa.ForeignKeyConstraint(["institute_id","campaign_id","original_id"],["marketing_campaign_originals.institute_id","marketing_campaign_originals.campaign_id","marketing_campaign_originals.id"],name="fk_marketing_campaign_head"))
def downgrade():
    if context.is_offline_mode():raise RuntimeError("Marketing history verification requires online downgrade")
    tables=("marketing_campaign_heads","marketing_campaign_originals","marketing_template_heads","marketing_template_originals")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables):raise RuntimeError("Recorded campaign/template history cannot be removed by downgrade")
    for table in tables:op.drop_table(table)
