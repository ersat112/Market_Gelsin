import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "turkiye_market_platform.db"


LATEST_RUNS_CTE = """
WITH latest_runs AS (
    SELECT market_key, city_plate_code, MAX(run_id) AS run_id
    FROM scrape_runs
    WHERE status IN ('completed', 'completed_with_errors')
    GROUP BY market_key, city_plate_code
)
"""


def _scalar(connection: sqlite3.Connection, sql: str) -> int:
    return int(connection.execute(sql).fetchone()[0] or 0)


def main() -> int:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        latest_runs = _scalar(
            connection,
            f"""
            {LATEST_RUNS_CTE}
            SELECT COUNT(*) FROM latest_runs
            """,
        )
        latest_offer_row = connection.execute(
            f"""
            {LATEST_RUNS_CTE}
            SELECT
                COUNT(*) AS offers_latest,
                SUM(CASE WHEN image_url IS NOT NULL AND image_url != '' THEN 1 ELSE 0 END) AS offers_with_image,
                SUM(CASE WHEN source_barcode IS NOT NULL AND source_barcode != '' THEN 1 ELSE 0 END) AS offers_with_barcode,
                SUM(CASE WHEN canonical_id IS NOT NULL AND canonical_id != '' THEN 1 ELSE 0 END) AS offers_with_canonical
            FROM offers
            WHERE run_id IN (SELECT run_id FROM latest_runs)
            """
        ).fetchone()
        current_shared_snapshot_rows = _scalar(
            connection,
            f"""
            {LATEST_RUNS_CTE}
            SELECT COUNT(*)
            FROM shared_catalog_city_runs city_runs
            JOIN shared_catalog_snapshot_items items
              ON items.snapshot_id = city_runs.snapshot_id
            WHERE city_runs.run_id IN (SELECT run_id FROM latest_runs)
            """,
        )

        stats = {
            "sqlite_db_path": str(DB_PATH),
            "offers_total": _scalar(connection, "SELECT COUNT(*) FROM offers"),
            "raw_products_total": _scalar(connection, "SELECT COUNT(*) FROM raw_products"),
            "scrape_runs_total": _scalar(connection, "SELECT COUNT(*) FROM scrape_runs"),
            "canonical_products_total": _scalar(connection, "SELECT COUNT(*) FROM canonical_products"),
            "canonical_product_barcodes_total": _scalar(connection, "SELECT COUNT(*) FROM canonical_product_barcodes"),
            "latest_successful_runs": latest_runs,
            "offers_latest_runs": int(latest_offer_row["offers_latest"] or 0),
            "offers_latest_with_image": int(latest_offer_row["offers_with_image"] or 0),
            "offers_latest_with_barcode": int(latest_offer_row["offers_with_barcode"] or 0),
            "offers_latest_with_canonical": int(latest_offer_row["offers_with_canonical"] or 0),
            "offers_latest_with_image_ratio": round(
                (int(latest_offer_row["offers_with_image"] or 0) / int(latest_offer_row["offers_latest"] or 1)),
                4,
            ),
            "offers_latest_with_barcode_ratio": round(
                (int(latest_offer_row["offers_with_barcode"] or 0) / int(latest_offer_row["offers_latest"] or 1)),
                4,
            ),
            "current_offer_rows_estimate": int(latest_offer_row["offers_latest"] or 0) + current_shared_snapshot_rows,
            "shared_catalog_rows_current": current_shared_snapshot_rows,
            "barcode_scan_events_total": _scalar(connection, "SELECT COUNT(*) FROM barcode_scan_events"),
            "barcode_scan_signals_total": _scalar(connection, "SELECT COUNT(*) FROM barcode_scan_signals"),
        }
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
