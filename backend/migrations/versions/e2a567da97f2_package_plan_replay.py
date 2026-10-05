"""Replay-safe package configuration; retain legacy plans without replay keys."""
from alembic import op
import sqlalchemy as sa

revision = "e2a567da97f2"
down_revision = "d1f456c986e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("package_plans") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(120), nullable=True))
        batch.add_column(sa.Column("creation_fingerprint", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_package_plan_creation_replay", ["institute_id", "idempotency_key"])
        batch.create_check_constraint("ck_package_plan_creation_replay",
            "(idempotency_key IS NULL AND creation_fingerprint IS NULL) OR "
            "(idempotency_key IS NOT NULL AND creation_fingerprint IS NOT NULL)")


def downgrade():
    if op.get_bind().execute(sa.text(
            "SELECT id FROM package_plans WHERE idempotency_key IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Replay-keyed package plans exist; downgrade cannot preserve creation recovery")
    with op.batch_alter_table("package_plans") as batch:
        batch.drop_constraint("ck_package_plan_creation_replay", type_="check")
        batch.drop_constraint("uq_package_plan_creation_replay", type_="unique")
        batch.drop_column("creation_fingerprint")
        batch.drop_column("idempotency_key")
