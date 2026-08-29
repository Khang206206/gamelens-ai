import logging
from collections.abc import Generator

from sqlalchemy import Engine, bindparam, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

DATABASE_CONNECT_TIMEOUT_SECONDS = 1
EXPECTED_SCHEMA_REVISION = "0007_stage_5_artifact_registry"
REQUIRED_SCHEMA_TABLES = (
    "games",
    "genres",
    "tags",
    "platforms",
    "game_genres",
    "game_tags",
    "game_platforms",
    "users",
    "user_preferences",
    "interactions",
    "recommendation_events",
    "collaborative_contribution_consents",
    "collaborative_data_revision",
)
REQUIRED_TABLE_COUNT_QUERY = text(
    """
    SELECT count(*)
    FROM information_schema.tables
    WHERE table_schema = current_schema()
      AND table_name IN :required_tables
    """
).bindparams(bindparam("required_tables", expanding=True))
SCHEMA_REVISION_QUERY = text(
    """
    SELECT count(*) = 1
       AND max(version_num) = :expected_revision
    FROM alembic_version
    """
)


def create_database_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS},
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


def begin_repeatable_read(session: Session, *, read_only: bool) -> None:
    """Establish transaction mode before the owner's first application query."""

    _begin_transaction(session, isolation_level="REPEATABLE READ", read_only=read_only)


def begin_read_committed(session: Session, *, read_only: bool = False) -> None:
    """Use lock-serialized READ COMMITTED semantics for ordinary profile mutations."""

    _begin_transaction(session, isolation_level="READ COMMITTED", read_only=read_only)


def _begin_transaction(
    session: Session,
    *,
    isolation_level: str,
    read_only: bool,
) -> None:
    """Establish a fixed transaction mode before the owner's first application query."""

    if session.in_transaction():
        raise RuntimeError("Transaction mode must be established before the first query")
    if session.get_bind().dialect.name == "postgresql":
        mode = "READ ONLY" if read_only else "READ WRITE"
        session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}, {mode}"))
    else:
        session.begin()


def session_scope(factory: sessionmaker[Session]) -> Generator[Session]:
    """Yield one session without committing implicitly.

    Write use cases own their transaction and must commit explicitly. The
    dependency only rolls back failures and always releases the session.
    """

    session = factory()
    try:
        yield session
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def database_is_ready(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            table_count = connection.scalar(
                REQUIRED_TABLE_COUNT_QUERY,
                {"required_tables": REQUIRED_SCHEMA_TABLES},
            )
            revision_ready = connection.scalar(
                SCHEMA_REVISION_QUERY,
                {"expected_revision": EXPECTED_SCHEMA_REVISION},
            )
    except SQLAlchemyError as error:
        logger.warning(
            "Database readiness check failed",
            extra={"error_type": type(error).__name__},
        )
        return False
    return table_count == len(REQUIRED_SCHEMA_TABLES) and revision_ready is True
