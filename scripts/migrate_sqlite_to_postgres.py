import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nationwide_platform.env_loader import load_local_env_files


load_local_env_files()


SQLITE_DB_PATH = ROOT / "turkiye_market_platform.db"
DEFAULT_BATCH_SIZE = 10_000

POSTGRES_RUNTIME_VIEWS_SQL = """
DROP VIEW IF EXISTS current_offers CASCADE;
DROP VIEW IF EXISTS effective_offers CASCADE;

CREATE VIEW effective_offers AS
SELECT
    offers.offer_id,
    offers.canonical_id,
    offers.market_key,
    offers.city_plate_code,
    offers.source_product_id,
    offers.source_barcode,
    offers.display_name,
    offers.listed_price,
    offers.promo_price,
    offers.availability,
    offers.unit_label,
    COALESCE(
        offers.image_url,
        (
            SELECT rp.image_url
            FROM raw_products rp
            WHERE rp.run_id = offers.run_id
              AND (
                    (offers.source_product_id IS NOT NULL AND rp.source_product_id = offers.source_product_id)
                 OR (offers.source_product_id IS NULL AND rp.source_name = offers.display_name)
              )
            ORDER BY rp.raw_id DESC
            LIMIT 1
        )
    ) AS image_url,
    offers.observed_at,
    offers.run_id
FROM offers
UNION ALL
SELECT
    NULL AS offer_id,
    items.canonical_id,
    city_runs.market_key,
    city_runs.city_plate_code,
    items.source_product_id,
    items.source_barcode,
    items.display_name,
    items.listed_price,
    items.promo_price,
    items.availability,
    items.unit_label,
    items.image_url,
    items.observed_at,
    city_runs.run_id
FROM shared_catalog_city_runs city_runs
JOIN shared_catalog_snapshot_items items
    ON items.snapshot_id = city_runs.snapshot_id;

CREATE VIEW current_offers AS
WITH latest_successful_runs AS (
    SELECT
        market_key,
        city_plate_code,
        MAX(run_id) AS run_id
    FROM scrape_runs
    WHERE status IN ('completed', 'completed_with_errors')
    GROUP BY market_key, city_plate_code
)
SELECT
    offers.offer_id,
    offers.canonical_id,
    offers.market_key,
    offers.city_plate_code,
    offers.source_product_id,
    offers.source_barcode,
    offers.display_name,
    offers.listed_price,
    offers.promo_price,
    offers.availability,
    offers.unit_label,
    offers.image_url,
    offers.observed_at,
    offers.run_id
FROM effective_offers offers
INNER JOIN latest_successful_runs
    ON latest_successful_runs.run_id = offers.run_id;
"""


def _db_url() -> str:
    for key in ("MARKET_GELSIN_DB_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise SystemExit("MARKET_GELSIN_DB_URL or DATABASE_URL is required")


def _table_names(connection: sqlite3.Connection) -> List[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [row[0] for row in rows]


def _table_sql(connection: sqlite3.Connection, table_name: str) -> str:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row[0] if row and row[0] else ""


def _table_info(connection: sqlite3.Connection, table_name: str) -> List[Dict[str, object]]:
    columns = []
    for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall():
        columns.append(
            {
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "notnull": bool(row[3]),
                "default": row[4],
                "pk_order": int(row[5]),
            }
        )
    return columns


def _index_definitions(connection: sqlite3.Connection, table_name: str) -> List[Dict[str, object]]:
    indexes: List[Dict[str, object]] = []
    for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall():
        index_name = row[1]
        is_unique = bool(row[2])
        origin = row[3] if len(row) > 3 else "c"
        if origin == "pk":
            continue
        columns = [item[2] for item in connection.execute(f"PRAGMA index_info({index_name})").fetchall()]
        if not columns:
            continue
        indexes.append(
            {
                "name": index_name,
                "unique": is_unique,
                "origin": origin,
                "columns": columns,
            }
        )
    return indexes


def _postgres_type(sqlite_type: str) -> str:
    normalized = (sqlite_type or "").strip().upper()
    if "INT" in normalized:
        return "BIGINT"
    if any(token in normalized for token in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE PRECISION"
    if "BLOB" in normalized:
        return "BYTEA"
    return "TEXT"


def _is_identity_column(table_sql: str, column_name: str, column_type: str, pk_order: int) -> bool:
    if pk_order != 1:
        return False
    if "INT" not in (column_type or "").upper():
        return False
    lowered = table_sql.lower()
    identity_patterns = [
        f"{column_name.lower()} integer primary key autoincrement",
        f"{column_name.lower()} integer primary key",
    ]
    return any(pattern in lowered for pattern in identity_patterns)


def _postgres_default(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _create_table_sql(table_name: str, columns: List[Dict[str, object]], table_sql: str) -> Tuple[str, List[str]]:
    pk_columns = [column["name"] for column in sorted(columns, key=lambda item: item["pk_order"]) if column["pk_order"]]
    identity_columns: List[str] = []
    column_lines: List[str] = []

    for column in columns:
        column_name = column["name"]
        column_type = _postgres_type(str(column["type"]))
        is_identity = _is_identity_column(table_sql, str(column_name), str(column["type"]), int(column["pk_order"]))
        line = f'"{column_name}" {column_type}'
        if is_identity:
            line += " GENERATED BY DEFAULT AS IDENTITY"
            identity_columns.append(str(column_name))
        default = _postgres_default(column["default"])
        if default is not None:
            line += f" DEFAULT {default}"
        if column["notnull"]:
            line += " NOT NULL"
        column_lines.append(line)

    if pk_columns:
        if len(pk_columns) == 1 and pk_columns[0] in identity_columns:
            column_lines = [
                f'{line} PRIMARY KEY' if line.startswith(f'"{pk_columns[0]}" ') else line
                for line in column_lines
            ]
        else:
            pk_expr = ", ".join(f'"{name}"' for name in pk_columns)
            column_lines.append(f"PRIMARY KEY ({pk_expr})")

    sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n    ' + ",\n    ".join(column_lines) + "\n)"
    return sql, identity_columns


def _truncate_table(connection, table_name: str) -> None:
    connection.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE')


def _copy_table(sqlite_connection: sqlite3.Connection, postgres_connection, table_name: str, batch_size: int) -> int:
    columns = [column["name"] for column in _table_info(sqlite_connection, table_name)]
    quoted_columns = ", ".join(f'"{name}"' for name in columns)
    sqlite_cursor = sqlite_connection.execute(f'SELECT {", ".join(columns)} FROM "{table_name}"')
    copied = 0
    with postgres_connection.cursor() as cursor:
        with cursor.copy(f'COPY "{table_name}" ({quoted_columns}) FROM STDIN') as copy:
            while True:
                rows = sqlite_cursor.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    copy.write_row(row)
                copied += len(rows)
    return copied


def _set_identity_sequences(connection, table_name: str, identity_columns: Sequence[str]) -> None:
    with connection.cursor() as cursor:
        for column_name in identity_columns:
            cursor.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(%s, %s),
                    COALESCE((SELECT MAX("{column_name}") FROM "{table_name}"), 1),
                    true
                )
                """,
                (table_name, column_name),
            )


def _create_indexes(connection, table_name: str, indexes: List[Dict[str, object]]) -> None:
    for index in indexes:
        original_name = str(index["name"])
        if original_name.startswith("sqlite_autoindex"):
            suffix = "_".join(index["columns"])
            index_name = f'ux_{table_name}_{suffix}'
        else:
            index_name = original_name
        uniqueness = "UNIQUE " if index["unique"] else ""
        column_expr = ", ".join(f'"{column}"' for column in index["columns"])
        connection.execute(
            f'CREATE {uniqueness}INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ({column_expr})'
        )


def _create_runtime_views(connection) -> None:
    for statement in [part.strip() for part in POSTGRES_RUNTIME_VIEWS_SQL.split(";") if part.strip()]:
        connection.execute(statement)


def main() -> int:
    batch_size = int(os.getenv("MARKET_GELSIN_MIGRATION_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
    selected_tables = {
        item.strip()
        for item in os.getenv("MARKET_GELSIN_MIGRATION_TABLES", "").split(",")
        if item.strip()
    }
    if len(sys.argv) > 1:
        batch_size = int(sys.argv[1])
    if len(sys.argv) > 2:
        selected_tables = {item.strip() for item in sys.argv[2].split(",") if item.strip()}

    sqlite_uri = f"file:{SQLITE_DB_PATH}?mode=ro"
    with sqlite3.connect(sqlite_uri, uri=True) as sqlite_connection:
        sqlite_connection.row_factory = sqlite3.Row
        sqlite_connection.execute("PRAGMA query_only = TRUE")
        table_names = _table_names(sqlite_connection)
        if selected_tables:
            table_names = [table_name for table_name in table_names if table_name in selected_tables]

        with psycopg.connect(_db_url()) as postgres_connection:
            with postgres_connection.cursor() as cursor:
                cursor.execute("SET statement_timeout TO 0")

            summary: List[Tuple[str, int]] = []
            for table_name in table_names:
                columns = _table_info(sqlite_connection, table_name)
                table_sql = _table_sql(sqlite_connection, table_name)
                create_sql, identity_columns = _create_table_sql(table_name, columns, table_sql)
                postgres_connection.execute(create_sql)
                _truncate_table(postgres_connection, table_name)
                copied = _copy_table(sqlite_connection, postgres_connection, table_name, batch_size)
                if identity_columns:
                    _set_identity_sequences(postgres_connection, table_name, identity_columns)
                _create_indexes(postgres_connection, table_name, _index_definitions(sqlite_connection, table_name))
                summary.append((table_name, copied))
                postgres_connection.commit()

            _create_runtime_views(postgres_connection)
            postgres_connection.commit()

    print("SQLite -> PostgreSQL migration tamamlandi.")
    for table_name, copied in summary:
        print(f"- {table_name}: {copied} satir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
