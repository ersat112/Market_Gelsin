import sqlite3

from nationwide_platform.bootstrap import bootstrap_database


def main() -> int:
    bootstrap_database()
    connection = sqlite3.connect("/Users/ersat/Desktop/Market_Gelsin/turkiye_market_platform.db")
    cursor = connection.cursor()
    rows = cursor.execute(
        """
        SELECT market_key, adapter_family, city_target_count, complexity_level, priority_score, recommended_next_step
        FROM adapter_onboarding_backlog
        ORDER BY priority_score DESC, city_target_count DESC, market_key
        LIMIT 20
        """
    ).fetchall()
    print("Top adapter onboarding backlog:")
    for market_key, adapter_family, city_target_count, complexity_level, priority_score, next_step in rows:
        print(
            f"- {market_key}: family={adapter_family}, cities={city_target_count}, "
            f"complexity={complexity_level}, priority={priority_score}"
        )
        print(f"  next: {next_step}")
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
