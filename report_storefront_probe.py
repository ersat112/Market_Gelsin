import sqlite3

from nationwide_platform.bootstrap import bootstrap_database


def main() -> int:
    bootstrap_database()
    connection = sqlite3.connect("/Users/ersat/Desktop/Market_Gelsin/turkiye_market_platform.db")
    cursor = connection.cursor()

    summary_rows = cursor.execute(
        """
        SELECT product_flow_status, COUNT(*)
        FROM market_storefront_probes
        GROUP BY product_flow_status
        ORDER BY COUNT(*) DESC, product_flow_status
        """
    ).fetchall()
    print("Storefront Probe Ozeti")
    for status, count in summary_rows:
        print(f"- {status}: {count}")

    actionable_rows = cursor.execute(
        """
        SELECT market_key, storefront_family, recommended_adapter_family, sample_product_count, sample_url
        FROM market_storefront_probes
        WHERE product_flow_status = 'open_product_flow'
        ORDER BY sample_product_count DESC, market_key
        LIMIT 20
        """
    ).fetchall()
    print("\nAcilabilir Marketler")
    for market_key, family, adapter_family, sample_product_count, sample_url in actionable_rows:
        print(
            f"- {market_key}: family={family}, adapter={adapter_family}, "
            f"sample_count={sample_product_count}"
        )
        if sample_url:
            print(f"  sample={sample_url}")

    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
