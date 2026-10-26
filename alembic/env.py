from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import storage.models  # noqa: F401 - registers all models on Base.metadata
from alembic import context
from storage.db import _SQLALCHEMY_DATABASE_URL
from storage.models.base import Base

config = context.config

# Escape literal '%' as '%%' because set_main_option stores the value in a
# ConfigParser, which applies %-interpolation.
config.set_main_option("sqlalchemy.url", _SQLALCHEMY_DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
