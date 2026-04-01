from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from .runner import _ensure_shared_catalog_snapshot
from .storage import connect


SUCCESSFUL_RUN_STATUSES = ("completed", "completed_with_errors")
DEFAULT_SEED_CITY_PLATE_CODE = 34

# National chains and national cosmetics can be stored as a shared reference catalog
# for our comparison use case. City-specific deltas can be reintroduced later as overrides.
SHARED_REFERENCE_MARKETS = {
    "a101_kapida",
    "bim_market",
    "bizim_toptan_online",
    "carrefoursa_online_market",
    "cepte_sok",
    "eveshop_online",
    "flormar_online",
    "getir_buyuk",
    "gratis_online",
    "kozmela_online",
    "migros_sanal_market",
    "rossmann_online",
    "tarim_kredi_koop_market",
    "tshop_online",
}


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _latest_successful_runs(connection, market_key: str) -> List[Dict[str, int]]:
    rows = connection.execute(
        """
        WITH ranked_runs AS (
            SELECT
                run_id,
                city_plate_code,
                stored_count,
                ROW_NUMBER() OVER (
                    PARTITION BY city_plate_code
                    ORDER BY run_id DESC
                ) AS row_num
            FROM scrape_runs
            WHERE market_key = ?
              AND status IN (?, ?)
        )
        SELECT run_id, city_plate_code, stored_count
        FROM ranked_runs
        WHERE row_num = 1
        ORDER BY city_plate_code
        """,
        (market_key, SUCCESSFUL_RUN_STATUSES[0], SUCCESSFUL_RUN_STATUSES[1]),
    ).fetchall()
    return [
        {
            "run_id": int(row[0]),
            "city_plate_code": int(row[1]),
            "stored_count": int(row[2] or 0),
        }
        for row in rows
    ]


def _select_seed_run(latest_runs: Sequence[Dict[str, int]], preferred_city_plate_code: int) -> Dict[str, int]:
    preferred = next((row for row in latest_runs if row["city_plate_code"] == preferred_city_plate_code), None)
    if preferred is not None:
        return preferred
    return max(latest_runs, key=lambda row: (row["stored_count"], row["run_id"]))


def _select_seed_run_with_materialized_offers(
    connection,
    market_key: str,
    latest_runs: Sequence[Dict[str, int]],
    preferred_city_plate_code: int,
) -> Dict[str, int]:
    latest_run_by_city = {row["city_plate_code"]: row for row in latest_runs}
    seed_rows = connection.execute(
        """
        SELECT
            run_id,
            city_plate_code,
            stored_count,
            (SELECT COUNT(*) FROM offers WHERE run_id = scrape_runs.run_id) AS offer_row_count
        FROM scrape_runs
        WHERE market_key = ?
          AND status IN (?, ?)
        ORDER BY
            CASE WHEN city_plate_code = ? THEN 0 ELSE 1 END,
            offer_row_count DESC,
            stored_count DESC,
            run_id DESC
        """,
        (
            market_key,
            SUCCESSFUL_RUN_STATUSES[0],
            SUCCESSFUL_RUN_STATUSES[1],
            preferred_city_plate_code,
        ),
    ).fetchall()
    for row in seed_rows:
        if int(row[3] or 0) > 0:
            city_plate_code = int(row[1])
            if city_plate_code in latest_run_by_city:
                return {
                    "run_id": int(row[0]),
                    "city_plate_code": city_plate_code,
                    "stored_count": int(row[2] or 0),
                }
    return _select_seed_run(latest_runs, preferred_city_plate_code)


def backfill_shared_snapshot_for_market(
    market_key: str,
    preferred_city_plate_code: int = DEFAULT_SEED_CITY_PLATE_CODE,
    compact_materialized_offers: bool = True,
) -> Dict[str, int]:
    with connect() as connection:
        latest_runs = _latest_successful_runs(connection, market_key)
        if not latest_runs:
            return {
                "market_key": market_key,
                "city_count": 0,
                "seed_run_id": 0,
                "snapshot_id": 0,
                "snapshot_item_count": 0,
                "deleted_offer_rows": 0,
                "deleted_raw_rows": 0,
            }

        seed_run = _select_seed_run_with_materialized_offers(
            connection=connection,
            market_key=market_key,
            latest_runs=latest_runs,
            preferred_city_plate_code=preferred_city_plate_code,
        )
        snapshot_id, snapshot_item_count = _ensure_shared_catalog_snapshot(
            connection=connection,
            market_key=market_key,
            seed_run_id=seed_run["run_id"],
            seed_city_plate_code=seed_run["city_plate_code"],
        )
        connection.commit()

        cloned_at = _now()
        connection.execute("BEGIN")
        try:
            connection.executemany(
                """
                INSERT INTO shared_catalog_city_runs (
                    run_id,
                    snapshot_id,
                    market_key,
                    city_plate_code,
                    seed_run_id,
                    cloned_at,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    snapshot_id = excluded.snapshot_id,
                    market_key = excluded.market_key,
                    city_plate_code = excluded.city_plate_code,
                    seed_run_id = excluded.seed_run_id,
                    cloned_at = excluded.cloned_at,
                    notes = excluded.notes
                """,
                [
                    (
                        row["run_id"],
                        snapshot_id,
                        market_key,
                        row["city_plate_code"],
                        seed_run["run_id"],
                        cloned_at,
                        f"shared_snapshot_backfill:{snapshot_id}:seed:{seed_run['run_id']}",
                    )
                    for row in latest_runs
                ],
            )

            deleted_offer_rows = 0
            deleted_raw_rows = 0
            if compact_materialized_offers:
                run_ids = [row["run_id"] for row in latest_runs]
                placeholders = ",".join("?" for _ in run_ids)
                deleted_offer_rows = connection.execute(
                    f"SELECT COUNT(*) FROM offers WHERE run_id IN ({placeholders})",
                    tuple(run_ids),
                ).fetchone()[0]
                connection.execute(
                    f"DELETE FROM offers WHERE run_id IN ({placeholders})",
                    tuple(run_ids),
                )

                clone_run_ids = [row["run_id"] for row in latest_runs if row["run_id"] != seed_run["run_id"]]
                if clone_run_ids:
                    clone_placeholders = ",".join("?" for _ in clone_run_ids)
                    deleted_raw_rows = connection.execute(
                        f"SELECT COUNT(*) FROM raw_products WHERE run_id IN ({clone_placeholders})",
                        tuple(clone_run_ids),
                    ).fetchone()[0]
                    connection.execute(
                        f"DELETE FROM raw_products WHERE run_id IN ({clone_placeholders})",
                        tuple(clone_run_ids),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return {
        "market_key": market_key,
        "city_count": len(latest_runs),
        "seed_run_id": seed_run["run_id"],
        "snapshot_id": snapshot_id,
        "snapshot_item_count": snapshot_item_count,
        "deleted_offer_rows": int(deleted_offer_rows),
        "deleted_raw_rows": int(deleted_raw_rows),
    }


def backfill_all_shared_snapshots(
    market_keys: Optional[Iterable[str]] = None,
    preferred_city_plate_code: int = DEFAULT_SEED_CITY_PLATE_CODE,
    compact_materialized_offers: bool = True,
) -> Dict[str, object]:
    selected_market_keys = list(market_keys or sorted(SHARED_REFERENCE_MARKETS))
    results = [
        backfill_shared_snapshot_for_market(
            market_key=market_key,
            preferred_city_plate_code=preferred_city_plate_code,
            compact_materialized_offers=compact_materialized_offers,
        )
        for market_key in selected_market_keys
    ]
    return {
        "market_count": len(results),
        "snapshot_count": sum(1 for row in results if row["snapshot_id"]),
        "total_snapshot_items": sum(int(row["snapshot_item_count"]) for row in results),
        "total_deleted_offer_rows": sum(int(row["deleted_offer_rows"]) for row in results),
        "total_deleted_raw_rows": sum(int(row["deleted_raw_rows"]) for row in results),
        "results": results,
    }
