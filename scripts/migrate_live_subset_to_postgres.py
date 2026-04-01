import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nationwide_platform.env_loader import load_local_env_files  # noqa: E402
from scripts.migrate_sqlite_to_postgres import (  # noqa: E402
    POSTGRES_RUNTIME_VIEWS_SQL,
    SQLITE_DB_PATH,
    _copy_table,
    _create_indexes,
    _create_table_sql,
    _create_runtime_views,
    _db_url,
    _index_definitions,
    _set_identity_sequences,
    _table_info,
    _table_names,
    _table_sql,
    _truncate_table,
)


load_local_env_files()


DEFAULT_BATCH_SIZE = 10_000
DEFAULT_PROFILE = "latest_full"
PROGRESS_LOG_EVERY = 100_000
FULL_TABLES = {
    "cities",
    "source_markets",
    "market_city_targets",
    "city_collection_program",
    "market_refresh_policy",
    "canonical_products",
    "canonical_product_barcodes",
    "city_local_discovery_tasks",
    "city_local_discovery_queries",
    "city_local_coverage_status",
    "city_controlled_flow_plan",
    "market_adapter_readiness",
    "adapter_onboarding_backlog",
    "barcode_scan_signals",
    "barcode_scan_events",
    "hot_product_refresh_candidates",
    "local_market_candidates",
    "market_storefront_probes",
}
SCHEMA_ONLY_TABLES_BY_PROFILE = {
    "latest_full": set(),
    "lean_current": {"raw_products"},
    "full_history": set(),
}


def _fetch_ids(connection: sqlite3.Connection, sql: str, params: Sequence = ()) -> List[int]:
    return [int(row[0]) for row in connection.execute(sql, params).fetchall()]


def _latest_successful_run_ids(connection: sqlite3.Connection) -> Set[int]:
    return set(
        _fetch_ids(
            connection,
            """
            SELECT run_id
            FROM (
                SELECT MAX(run_id) AS run_id
                FROM scrape_runs
                WHERE status IN ('completed', 'completed_with_errors')
                GROUP BY market_key, city_plate_code
            )
            """,
        )
    )


def _selected_snapshot_ids(connection: sqlite3.Connection, latest_run_ids: Set[int]) -> Set[int]:
    if not latest_run_ids:
        return set()
    placeholders = ",".join("?" for _ in latest_run_ids)
    return set(
        _fetch_ids(
            connection,
            f"""
            SELECT DISTINCT snapshot_id
            FROM shared_catalog_city_runs
            WHERE run_id IN ({placeholders})
            """,
            tuple(sorted(latest_run_ids)),
        )
    )


def _seed_run_ids_for_snapshots(connection: sqlite3.Connection, snapshot_ids: Set[int]) -> Set[int]:
    if not snapshot_ids:
        return set()
    placeholders = ",".join("?" for _ in snapshot_ids)
    return set(
        _fetch_ids(
            connection,
            f"""
            SELECT DISTINCT seed_run_id
            FROM shared_catalog_snapshots
            WHERE snapshot_id IN ({placeholders})
            """,
            tuple(sorted(snapshot_ids)),
        )
    )


def _copy_filtered_table(
    sqlite_connection: sqlite3.Connection,
    postgres_connection,
    table_name: str,
    select_sql: str,
    batch_size: int,
) -> int:
    columns = [column["name"] for column in _table_info(sqlite_connection, table_name)]
    quoted_columns = ", ".join(f'"{name}"' for name in columns)
    sqlite_cursor = sqlite_connection.execute(select_sql)
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
                if copied and copied % PROGRESS_LOG_EVERY == 0:
                    print(f"[copy] {table_name}: {copied} rows")
    return copied


def _selected_row_count(sqlite_connection: sqlite3.Connection, select_sql: str) -> int:
    count_sql = f"SELECT COUNT(*) FROM ({select_sql}) AS subset"
    return int(sqlite_connection.execute(count_sql).fetchone()[0] or 0)


def _select_sql_for_table(
    table_name: str,
    latest_run_ids: Set[int],
    snapshot_ids: Set[int],
    all_run_ids: Set[int],
    profile: str,
) -> str:
    if profile == "full_history":
        return f'SELECT * FROM "{table_name}"'
    if table_name in FULL_TABLES:
        return f'SELECT * FROM "{table_name}"'
    if table_name == "scrape_runs":
        ids = ",".join(str(item) for item in sorted(all_run_ids)) or "NULL"
        return f'SELECT * FROM "scrape_runs" WHERE run_id IN ({ids})'
    if table_name == "offers":
        ids = ",".join(str(item) for item in sorted(all_run_ids)) or "NULL"
        return f'SELECT * FROM "offers" WHERE run_id IN ({ids})'
    if table_name == "raw_products":
        ids = ",".join(str(item) for item in sorted(all_run_ids)) or "NULL"
        return f'SELECT * FROM "raw_products" WHERE run_id IN ({ids})'
    if table_name == "shared_catalog_city_runs":
        ids = ",".join(str(item) for item in sorted(latest_run_ids)) or "NULL"
        return f'SELECT * FROM "shared_catalog_city_runs" WHERE run_id IN ({ids})'
    if table_name == "shared_catalog_snapshots":
        ids = ",".join(str(item) for item in sorted(snapshot_ids)) or "NULL"
        return f'SELECT * FROM "shared_catalog_snapshots" WHERE snapshot_id IN ({ids})'
    if table_name == "shared_catalog_snapshot_items":
        ids = ",".join(str(item) for item in sorted(snapshot_ids)) or "NULL"
        return f'SELECT * FROM "shared_catalog_snapshot_items" WHERE snapshot_id IN ({ids})'
    return f'SELECT * FROM "{table_name}"'


def _migration_profile() -> str:
    profile = os.getenv("MARKET_GELSIN_MIGRATION_PROFILE", DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
    if profile not in SCHEMA_ONLY_TABLES_BY_PROFILE:
        raise SystemExit(
            f"Unsupported MARKET_GELSIN_MIGRATION_PROFILE={profile!r}. "
            f"Supported values: {', '.join(sorted(SCHEMA_ONLY_TABLES_BY_PROFILE))}"
        )
    return profile


def main() -> int:
    batch_size = int(os.getenv("MARKET_GELSIN_MIGRATION_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
    profile = _migration_profile()
    dry_run = os.getenv("MARKET_GELSIN_MIGRATION_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
    if len(sys.argv) > 1:
        batch_size = int(sys.argv[1])
    if len(sys.argv) > 2 and sys.argv[2].strip():
        profile = sys.argv[2].strip()
        if profile not in SCHEMA_ONLY_TABLES_BY_PROFILE:
            raise SystemExit(
                f"Unsupported profile {profile!r}. Supported values: {', '.join(sorted(SCHEMA_ONLY_TABLES_BY_PROFILE))}"
            )
    if len(sys.argv) > 3:
        dry_run = sys.argv[3].strip().lower() in {"1", "true", "yes", "dry-run", "--dry-run"}

    sqlite_uri = f"file:{SQLITE_DB_PATH}?mode=ro"
    with sqlite3.connect(sqlite_uri, uri=True) as sqlite_connection:
        sqlite_connection.row_factory = sqlite3.Row
        sqlite_connection.execute("PRAGMA query_only = TRUE")
        table_names = _table_names(sqlite_connection)
        schema_only_tables = SCHEMA_ONLY_TABLES_BY_PROFILE[profile]

        latest_run_ids = _latest_successful_run_ids(sqlite_connection)
        snapshot_ids = _selected_snapshot_ids(sqlite_connection, latest_run_ids)
        seed_run_ids = _seed_run_ids_for_snapshots(sqlite_connection, snapshot_ids)
        all_run_ids = set(latest_run_ids) | set(seed_run_ids)

        if dry_run:
            print(f"profile={profile}")
            print(f"latest_run_ids={len(latest_run_ids)} snapshot_ids={len(snapshot_ids)} all_run_ids={len(all_run_ids)}")
            for table_name in table_names:
                select_sql = _select_sql_for_table(
                    table_name,
                    latest_run_ids,
                    snapshot_ids,
                    all_run_ids,
                    profile,
                )
                if table_name in schema_only_tables:
                    print(f"- {table_name}: 0 satir (schema only)")
                    continue
                selected_count = _selected_row_count(sqlite_connection, select_sql)
                print(f"- {table_name}: {selected_count} satir")
            return 0

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
                select_sql = _select_sql_for_table(
                    table_name,
                    latest_run_ids,
                    snapshot_ids,
                    all_run_ids,
                    profile,
                )
                if table_name in schema_only_tables:
                    copied = 0
                else:
                    copied = _copy_filtered_table(sqlite_connection, postgres_connection, table_name, select_sql, batch_size)
                if identity_columns:
                    _set_identity_sequences(postgres_connection, table_name, identity_columns)
                _create_indexes(postgres_connection, table_name, _index_definitions(sqlite_connection, table_name))
                summary.append((table_name, copied))
                postgres_connection.commit()

            _create_runtime_views(postgres_connection)
            postgres_connection.commit()

    print(f"Live subset SQLite -> PostgreSQL migration tamamlandi. profile={profile}")
    print(f"latest_run_ids={len(latest_run_ids)} snapshot_ids={len(snapshot_ids)} all_run_ids={len(all_run_ids)}")
    for table_name, copied in summary:
        print(f"- {table_name}: {copied} satir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
