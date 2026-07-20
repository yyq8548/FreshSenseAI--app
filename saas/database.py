"""Small SQLAlchemy Core adapter for FreshSense SaaS persistence.

The application keeps its repository API synchronous because model inference and
database calls already run in FastAPI's worker pool.  This adapter intentionally
exposes only the DB-API-shaped operations used by :mod:`saas.store` while adding
connection pooling, transactions, PostgreSQL support, and safe URL handling.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
import re
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, CursorResult, RowMapping
from sqlalchemy.exc import ArgumentError, NoSuchModuleError, SQLAlchemyError


class DatabaseConfigurationError(RuntimeError):
    """Raised when a database target is missing, unsupported, or malformed."""


class DatabaseOperationError(RuntimeError):
    """Raised when a database transaction cannot be completed."""


class Database:
    """Create short transactions against SQLite or PostgreSQL."""

    def __init__(self, target: str | Path) -> None:
        self.url, self.path, self.backend = normalize_database_target(target)
        connect_args: dict[str, Any] = {}
        if self.backend == "sqlite":
            connect_args = {"check_same_thread": False, "timeout": 10}
        try:
            self.engine = create_engine(
                self.url,
                connect_args=connect_args,
                future=True,
                pool_pre_ping=True,
                pool_recycle=300,
            )
        except (ArgumentError, NoSuchModuleError, ModuleNotFoundError) as exc:
            raise DatabaseConfigurationError(
                f"The {self.backend} database driver is unavailable or invalid."
            ) from exc
        if self.backend == "sqlite":
            event.listen(self.engine, "connect", _configure_sqlite_connection)

    @property
    def description(self) -> str:
        """Return a non-secret description suitable for logs and health data."""

        return self.backend

    @contextmanager
    def connect(self) -> Iterator["DatabaseConnection"]:
        """Open one transaction and commit or roll it back atomically."""

        try:
            with self.engine.begin() as connection:
                yield DatabaseConnection(connection)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                f"The {self.backend} database operation failed."
            ) from exc

    def dispose(self) -> None:
        self.engine.dispose()


class DatabaseConnection:
    """Compatibility layer for the small SQL surface used by ``SaaSStore``."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def execute(
        self,
        statement: str,
        parameters: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> "DatabaseResult":
        sql, values = bind_parameters(statement, parameters)
        result = self._connection.execute(text(sql), values)
        return DatabaseResult(result)

    def executescript(self, script: str) -> None:
        for statement in (part.strip() for part in script.split(";")):
            if statement:
                self._connection.execute(text(statement))


class DatabaseResult:
    def __init__(self, result: CursorResult[Any]) -> None:
        self._result = result

    @property
    def rowcount(self) -> int:
        return int(self._result.rowcount)

    def fetchone(self) -> RowMapping | None:
        return self._result.mappings().first()

    def fetchall(self) -> list[RowMapping]:
        return list(self._result.mappings().all())


def normalize_database_target(target: str | Path) -> tuple[str, Path | None, str]:
    """Normalize a local path or SQLAlchemy URL without exposing credentials."""

    raw = str(target).strip()
    if not raw:
        raise DatabaseConfigurationError("The SaaS database target is required.")
    if "://" not in raw:
        path = Path(raw).expanduser().resolve()
        return f"sqlite+pysqlite:///{path.as_posix()}", path, "sqlite"

    scheme = raw.split("://", 1)[0].lower()
    if scheme in {"postgres", "postgresql"}:
        return "postgresql+psycopg://" + raw.split("://", 1)[1], None, "postgresql"
    if scheme == "postgresql+psycopg":
        return raw, None, "postgresql"
    if scheme in {"sqlite", "sqlite+pysqlite"}:
        return raw, _sqlite_path_from_url(raw), "sqlite"
    raise DatabaseConfigurationError(
        "FreshSense SaaS persistence supports only SQLite and PostgreSQL."
    )


def bind_parameters(
    statement: str,
    parameters: Sequence[Any] | Mapping[str, Any] | None,
) -> tuple[str, Mapping[str, Any]]:
    """Convert existing positional placeholders to SQLAlchemy named binds."""

    if parameters is None:
        return statement, {}
    if isinstance(parameters, Mapping):
        return statement, parameters
    values = tuple(parameters)
    matches = list(re.finditer(r"\?", statement))
    if len(matches) != len(values):
        raise DatabaseConfigurationError(
            "The database statement parameter count is invalid."
        )
    names = iter(f"p{index}" for index in range(len(values)))
    sql = re.sub(r"\?", lambda _: f":{next(names)}", statement)
    return sql, {f"p{index}": value for index, value in enumerate(values)}


def _sqlite_path_from_url(url: str) -> Path | None:
    marker = "///"
    if marker not in url or ":memory:" in url:
        return None
    raw_path = url.split(marker, 1)[1].split("?", 1)[0]
    return Path(raw_path).resolve()


def _configure_sqlite_connection(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 10000")
    finally:
        cursor.close()


__all__ = [
    "Database",
    "DatabaseConfigurationError",
    "DatabaseConnection",
    "DatabaseOperationError",
    "bind_parameters",
    "normalize_database_target",
]
