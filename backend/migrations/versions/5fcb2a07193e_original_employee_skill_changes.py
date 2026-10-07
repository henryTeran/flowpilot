"""Original signed employee skill changes."""
from alembic import op, context
import sqlalchemy as sa

revision = "5fcb2a07193e"
down_revision = "4eba19f6082d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("employee_skill_changes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False),
        sa.Column("expected_skills", sa.JSON, nullable=False),
        sa.Column("skills", sa.JSON, nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_skill_change_employee_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_skill_change_replay"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Skill change history verification requires an online downgrade")
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM employee_skill_changes")).scalar():
        raise RuntimeError("Recorded skill change history cannot be removed by downgrade")
    op.drop_table("employee_skill_changes")
