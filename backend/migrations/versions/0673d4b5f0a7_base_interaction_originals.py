"""Retain scoped BASE interaction attempt/outcome hash chains."""
from alembic import op, context
import sqlalchemy as sa
revision = "0673d4b5f0a7"
down_revision = "f562c3a4edf6"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("base_interaction_originals",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("previous_id", sa.String(80), sa.ForeignKey("base_interaction_originals.id"), nullable=True),
        sa.Column("attempt_id", sa.String(80), sa.ForeignKey("base_interaction_originals.id"), nullable=True),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("institute_id", "sequence", name="uq_base_interaction_sequence"),
        sa.UniqueConstraint("institute_id", "attempt_id", name="uq_base_interaction_completion"))
    op.create_index("ix_base_interaction_history", "base_interaction_originals", ["institute_id", "sequence"])

def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("BASE interaction verification requires online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM base_interaction_originals")).scalar():
        raise RuntimeError("Retained BASE interactions cannot be removed by downgrade")
    op.drop_index("ix_base_interaction_history", table_name="base_interaction_originals")
    op.drop_table("base_interaction_originals")
