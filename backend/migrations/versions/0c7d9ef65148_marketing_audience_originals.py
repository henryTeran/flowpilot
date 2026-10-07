"""Owned immutable audience originals and bounded retained pages."""
from alembic import context, op
import sqlalchemy as sa
revision="0c7d9ef65148"
down_revision="fb6c8de54037"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("marketing_audience_originals",
        sa.Column("id",sa.String(80),primary_key=True),
        sa.Column("institute_id",sa.String(80),sa.ForeignKey("institutes.id"),nullable=False),
        sa.Column("actor_id",sa.String(160),nullable=False),sa.Column("reason",sa.String(240),nullable=False),
        sa.Column("idempotency_key",sa.String(120),nullable=False),sa.Column("captured_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("request",sa.JSON,nullable=False),sa.Column("summary",sa.JSON,nullable=False),
        sa.UniqueConstraint("institute_id","id",name="uq_marketing_audience_owner"),sa.UniqueConstraint("institute_id","idempotency_key",name="uq_marketing_audience_replay"))
    op.create_table("marketing_audience_pages",
        sa.Column("institute_id",sa.String(80),primary_key=True),sa.Column("capture_id",sa.String(80),primary_key=True),
        sa.Column("page_index",sa.Integer,primary_key=True),sa.Column("observation",sa.JSON,nullable=False),
        sa.ForeignKeyConstraint(["institute_id","capture_id"],["marketing_audience_originals.institute_id","marketing_audience_originals.id"],name="fk_marketing_audience_page_owner"),
        sa.CheckConstraint("page_index >= 0",name="ck_marketing_audience_page_index"))

def downgrade():
    if context.is_offline_mode():raise RuntimeError("Audience history verification requires an online downgrade")
    tables=("marketing_audience_pages","marketing_audience_originals")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables):
        raise RuntimeError("Recorded marketing audience history cannot be removed by downgrade")
    for table in tables:op.drop_table(table)
