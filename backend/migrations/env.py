from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.database.base import Base

# Ensure all SQLAlchemy models are imported before autogenerate.
from app.modules.appointments import models as appointments_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.employees import models as employees_models  # noqa: F401
from app.modules.institutes import models as institutes_models  # noqa: F401
from app.modules.planning import models as planning_models  # noqa: F401
from app.modules.services import models as services_models  # noqa: F401
from app.modules.tickets import models as tickets_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Keep Alembic aligned with the runtime DB URL from environment/settings.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
