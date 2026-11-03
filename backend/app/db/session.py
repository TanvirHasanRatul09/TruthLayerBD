from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import event, inspect
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings
from app.models.analysis import Analysis, ExtractionRecord, OcrRecord, ProviderEvent  # noqa: F401 - register tables
from app.models.evidence import ComparisonRecord, Evidence, RetrievalRun, VerificationRecord  # noqa: F401 - register tables
from app.models.dataset import DatasetMatch  # noqa: F401 - register tables

SCHEMA_VERSION = 1


def check_schema(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table in SQLModel.metadata.sorted_tables:
        if table.name not in tables:
            raise RuntimeError(f"Database schema is missing table {table.name}; restore or migrate the database.")
        actual = {column["name"] for column in inspector.get_columns(table.name)}
        missing = {column.name for column in table.columns} - actual
        if missing:
            raise RuntimeError(f"Database schema for {table.name} is missing columns {', '.join(sorted(missing))}; restore or migrate the database.")
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"Database schema version {version} is newer than this app supports ({SCHEMA_VERSION}).")
            if version == 0:
                connection.exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")


@lru_cache
def get_engine(database_url: str):
    if database_url.startswith("sqlite:"):
        database_file = database_url.removeprefix("sqlite:///")
        if database_file != ":memory:":
            Path(database_file).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite:") else {})
    if database_url.startswith("sqlite:"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
    try:
        SQLModel.metadata.create_all(engine)
        check_schema(engine)
    except Exception:
        engine.dispose()
        raise
    return engine


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine(get_settings().database_url)) as session:
        yield session
