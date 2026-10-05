"""Institute resources, qualifications, requirements and configuration facts.

Revision ID: a1c935e720d4
Revises: 8a4d71f0b2c9
"""
from alembic import op
import sqlalchemy as sa

revision = "a1c935e720d4"
down_revision = "8a4d71f0b2c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("resources",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.UniqueConstraint("institute_id", "name", name="uq_resource_institute_name"),
        sa.CheckConstraint("kind IN ('room','equipment','bed','chair','device')", name="ck_resource_kind"),
        sa.CheckConstraint("status IN ('active','inactive','maintenance')", name="ck_resource_status"))
    op.create_index("ix_resources_institute_id", "resources", ["institute_id"])
    op.create_table("employee_skills",
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("employee_id", sa.String(80), sa.ForeignKey("employees.id"), primary_key=True),
        sa.Column("skill_code", sa.Text(), primary_key=True))
    op.create_index("ix_employee_skills_institute_id", "employee_skills", ["institute_id"])
    op.create_table("service_requirements",
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), primary_key=True),
        sa.Column("service_id", sa.String(80), sa.ForeignKey("services.id"), primary_key=True),
        sa.Column("skill_code", sa.Text(), primary_key=True))
    op.create_table("resource_requirements",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("service_id", sa.String(80), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.UniqueConstraint("institute_id", "service_id", "kind", "capability", name="uq_resource_requirement"),
        sa.CheckConstraint("quantity >= 1 AND quantity <= 10", name="ck_resource_requirement_quantity"),
        sa.CheckConstraint("kind IN ('room','equipment','bed','chair','device')", name="ck_resource_requirement_kind"))
    op.create_index("ix_resource_requirements_institute_id", "resource_requirements", ["institute_id"])
    op.create_index("ix_resource_requirements_service_id", "resource_requirements", ["service_id"])
    op.create_table("resource_configuration_events",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("institute_id", sa.String(80), sa.ForeignKey("institutes.id"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("target_id", sa.String(80), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_resource_configuration_events_institute_id", "resource_configuration_events", ["institute_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""INSERT INTO employee_skills (institute_id, employee_id, skill_code)
            SELECT DISTINCT e.institute_id, e.id, s.value
            FROM employees e CROSS JOIN LATERAL json_array_elements_text(
                CASE WHEN json_typeof(e.skills)='array' THEN e.skills ELSE '[]'::json END) s(value)""")
    else:
        op.execute("""INSERT INTO employee_skills (institute_id, employee_id, skill_code)
            SELECT DISTINCT e.institute_id, e.id, s.value
            FROM employees e, json_each(e.skills) s WHERE s.type='text'""")


def downgrade():
    op.drop_table("resource_configuration_events")
    op.drop_table("resource_requirements")
    op.drop_table("service_requirements")
    op.drop_table("employee_skills")
    op.drop_table("resources")
