from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.db import models  # noqa: F401
from app.db.base import Base
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if config.attributes.get("connection") is None:
    database_url = config.attributes.get("database_url") or get_settings().database_url
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def configure_context(*, connection: Connection | None = None, url: str | None = None) -> None:
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        literal_binds=connection is None,
        dialect_opts={"paramstyle": "named"} if connection is None else None,
        compare_type=True,
        compare_server_default=True,
    )


def run_migrations_offline() -> None:
    configure_context(url=config.get_main_option("sqlalchemy.url"))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    configure_context(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        run_migrations(supplied_connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
