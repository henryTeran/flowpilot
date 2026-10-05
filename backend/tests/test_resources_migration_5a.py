import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.database.base import Base


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_resource_migration_backfills_and_preserves_legacy_skills(tmp_path, monkeypatch, database):
    admin = None
    schema = None
    if database == "postgresql":
        postgres_url = os.environ.get("FLOWPILOT_TEST_POSTGRES_URL")
        if not postgres_url:
            pytest.skip("Explicit validation PostgreSQL URL required")
        admin = create_engine(postgres_url)
        schema = "fp_migration_" + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = make_url(postgres_url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'resources-migration.db'}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    engine = create_engine(url)
    try:
        command.upgrade(config, "8a4d71f0b2c9")
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO companies (id,name,status) VALUES ('co','Co','active')"))
            connection.execute(text("INSERT INTO countries (id,company_id,code,name) VALUES ('country','co','CH','CH')"))
            connection.execute(text("INSERT INTO regions (id,country_id,name) VALUES ('region','country','Region')"))
            connection.execute(text("INSERT INTO institutes (id,region_id,name,city,timezone,status) VALUES ('inst','region','Institute','City','Europe/Berlin','active')"))
            connection.execute(text("INSERT INTO employees (id,institute_id,first_name,skills,status) VALUES ('emp','inst','Test',:skills,'available')"),
                               {"skills": json.dumps(["EPILATION", "SPECIAL", "SPECIAL"])})
            connection.execute(text("INSERT INTO service_categories (id,name,code) VALUES ('cat','Category','TEST')"))
            connection.execute(text("INSERT INTO services (id,category_id,name,duration_min,requires_machine,requires_appointment,status) VALUES ('svc','cat','Service',20,false,false,'active')"))
            connection.execute(text("INSERT INTO appointments (id,institute_id,service_id,employee_id,customer_name,start_time,end_time,status) VALUES ('appt','inst','svc','emp','Test','2026-10-05 10:00:00','2026-10-05 10:20:00','scheduled')"))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            codes = connection.execute(text("SELECT skill_code FROM employee_skills ORDER BY skill_code")).scalars().all()
            assert codes == ["EPILATION", "SPECIAL"]
            preserved = connection.execute(text("SELECT booked_start_time = start_time, booked_end_time = end_time, actual_start_time, actual_end_time FROM appointments WHERE id='appt'")).one()
            assert tuple(preserved) == (True, True, None, None)
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "8a4d71f0b2c9")
        with engine.connect() as connection:
            original = connection.execute(text("SELECT skills FROM employees WHERE id='emp'")).scalar_one()
            assert (json.loads(original) if isinstance(original, str) else original) == ["EPILATION", "SPECIAL", "SPECIAL"]
        command.upgrade(config, "head")
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
