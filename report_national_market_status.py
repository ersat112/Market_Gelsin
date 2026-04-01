from nationwide_platform.national_priority import build_national_market_priorities
from nationwide_platform.storage import connect


def main() -> None:
    priorities = build_national_market_priorities()
    with connect() as connection:
        print("Ulusal Market Veri Durumu")
        for row in priorities:
            run_count, successful_run_count, latest_status, latest_stored_count, latest_finished_at = connection.execute(
                """
                SELECT
                    COUNT(*) AS run_count,
                    SUM(CASE WHEN status IN ('completed', 'completed_with_errors') THEN 1 ELSE 0 END) AS successful_run_count,
                    COALESCE((
                        SELECT status
                        FROM scrape_runs
                        WHERE market_key = ?
                        ORDER BY finished_at DESC, run_id DESC
                        LIMIT 1
                    ), 'never_run') AS latest_status,
                    COALESCE((
                        SELECT stored_count
                        FROM scrape_runs
                        WHERE market_key = ?
                        ORDER BY finished_at DESC, run_id DESC
                        LIMIT 1
                    ), 0) AS latest_stored_count,
                    (
                        SELECT finished_at
                        FROM scrape_runs
                        WHERE market_key = ?
                        ORDER BY finished_at DESC, run_id DESC
                        LIMIT 1
                    ) AS latest_finished_at
                FROM scrape_runs
                WHERE market_key = ?
                """,
                (row.market_key, row.market_key, row.market_key, row.market_key),
            ).fetchone()

            offer_count, barcode_count = connection.execute(
                """
                SELECT
                    COUNT(*) AS offer_count,
                    SUM(CASE WHEN source_barcode IS NOT NULL AND source_barcode <> '' THEN 1 ELSE 0 END) AS barcode_count
                FROM offers
                WHERE market_key = ?
                """,
                (row.market_key,),
            ).fetchone()

            current_offer_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM current_offers
                WHERE market_key = ?
                """,
                (row.market_key,),
            ).fetchone()[0]

            print(
                f"- #{row.priority_rank} {row.market_name} ({row.market_key}) | "
                f"adapter={row.adapter_status}/{row.adapter_family} | "
                f"targets={row.city_target_count} | runs={run_count or 0} ok={successful_run_count or 0} | "
                f"offers={offer_count or 0} current={current_offer_count or 0} barkod={barcode_count or 0} | "
                f"latest={latest_status} stored={latest_stored_count or 0} at={latest_finished_at or '-'}"
            )


if __name__ == "__main__":
    main()
