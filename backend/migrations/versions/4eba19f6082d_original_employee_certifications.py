"""Original declared certifications and separate signed revocations."""
from alembic import op, context
import sqlalchemy as sa

revision = "4eba19f6082d"
down_revision = "3da908e5f70c"
branch_labels = None
depends_on = None


def provenance():
    return [sa.Column("reason", sa.String(240), nullable=False), sa.Column("actor_id", sa.String(160), nullable=False),
            sa.Column("idempotency_key", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("employee_certifications",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(80), nullable=False), sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(120), nullable=False), sa.Column("issuer", sa.String(120), nullable=False),
        sa.Column("reference", sa.String(160), nullable=False), sa.Column("issued_on", sa.Date, nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False), sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_certification_employee_owner"),
        sa.UniqueConstraint("institute_id", "id", name="uq_certification_owner"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_certification_replay"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_certification_interval"))
    op.create_index("ix_certification_employee_code", "employee_certifications", ["institute_id", "employee_id", "code", "valid_from", "valid_until"])
    op.create_table("certification_revocations",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("institute_id", sa.String(80), nullable=False),
        sa.Column("certification_id", sa.String(80), nullable=False), *provenance(),
        sa.ForeignKeyConstraint(["institute_id", "certification_id"], ["employee_certifications.institute_id", "employee_certifications.id"], name="fk_certification_revocation_owner"),
        sa.UniqueConstraint("institute_id", "certification_id", name="uq_certification_revoked_original"),
        sa.UniqueConstraint("institute_id", "idempotency_key", name="uq_certification_revocation_replay"))


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("Certification history verification requires an online downgrade")
    if any(op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
           for table in ("employee_certifications", "certification_revocations")):
        raise RuntimeError("Recorded certification history cannot be removed by downgrade")
    op.drop_table("certification_revocations")
    op.drop_index("ix_certification_employee_code", table_name="employee_certifications")
    op.drop_table("employee_certifications")
