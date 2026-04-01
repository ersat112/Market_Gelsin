import os
from typing import Iterable, Optional, Sequence

try:
    import psycopg
except ImportError:  # pragma: no cover - optional in local SQLite mode
    psycopg = None

from .storage import DEFAULT_DB_PATH, connect as connect_sqlite


def _runtime_db_url() -> Optional[str]:
    for key in ("MARKET_GELSIN_DB_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return None


def runtime_backend() -> str:
    db_url = _runtime_db_url()
    if db_url and db_url.startswith(("postgres://", "postgresql://")):
        return "postgres"
    return "sqlite"


def connect_runtime(db_path=DEFAULT_DB_PATH, timeout: float = 30.0):
    if runtime_backend() == "postgres":
        return PostgresConnectionWrapper(_runtime_db_url(), timeout=timeout)
    return connect_sqlite(db_path, timeout=timeout)


class PostgresCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self) -> None:
        self._cursor.close()


class PostgresConnectionWrapper:
    backend = "postgres"

    def __init__(self, db_url: str, timeout: float = 30.0):
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgreSQL runtime")
        self.db_url = db_url
        self.timeout = timeout
        self._conn = None

    @property
    def db_url_display(self) -> str:
        return self.db_url.rsplit("@", 1)[-1] if "@" in self.db_url else self.db_url

    def __enter__(self):
        connect_timeout = max(1, int(self.timeout))
        self._conn = psycopg.connect(self.db_url, connect_timeout=connect_timeout)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._conn is None:
            return
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, params: Optional[Sequence] = None):
        cursor = self._conn.cursor()
        cursor.execute(_translate_sql(sql), params or ())
        return PostgresCursorWrapper(cursor)

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence]):
        cursor = self._conn.cursor()
        cursor.executemany(_translate_sql(sql), seq_of_params)
        return PostgresCursorWrapper(cursor)

    def executescript(self, script: str) -> None:
        for statement in _split_sql_statements(script):
            self.execute(statement)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


def _translate_sql(sql: str) -> str:
    return sql.replace("?", "%s")


def _split_sql_statements(script: str):
    for statement in script.split(";"):
        cleaned = statement.strip()
        if cleaned:
            yield cleaned
