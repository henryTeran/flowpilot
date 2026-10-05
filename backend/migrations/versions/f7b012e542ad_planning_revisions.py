"""Committed, tenant-scoped planning invalidation revisions.

Revision ID: f7b012e542ad
Revises: e6a901df431c
"""
from alembic import op
import sqlalchemy as sa

revision = "f7b012e542ad"
down_revision = "e6a901df431c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("planning_revisions",
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), primary_key=True),
        sa.Column("revision", sa.BigInteger(), nullable=False))
    op.execute("INSERT INTO planning_revisions (institute_id, revision) SELECT id, 0 FROM institutes")


def downgrade():
    op.drop_table("planning_revisions")
