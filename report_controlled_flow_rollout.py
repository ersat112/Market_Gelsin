import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "turkiye_market_platform.db"


def main() -> int:
    with sqlite3.connect(str(DB_PATH)) as connection:
        print("Kontrollu Canli Akis Rollout Ozeti")
        print(f"DB: {DB_PATH}")
        print()

        print("Asama sayilari")
        for stage, count in connection.execute(
            """
            SELECT rollout_stage, COUNT(*)
            FROM city_controlled_flow_plan
            GROUP BY rollout_stage
            ORDER BY rollout_stage
            """
        ):
            print(f"- {stage}: {count}")

        print()
        print("Sehir bazli plan")
        for row in connection.execute(
            """
            SELECT
                c.name,
                p.rollout_stage,
                COALESCE(p.primary_market_key, '-'),
                COALESCE(p.fallback_market_key, '-'),
                p.verified_market_count,
                p.live_market_count
            FROM city_controlled_flow_plan p
            JOIN cities c ON c.plate_code = p.city_plate_code
            ORDER BY c.plate_code
            """
        ):
            city_name, stage, primary_market, fallback_market, verified_count, live_count = row
            print(
                f"- {city_name}: stage={stage} primary={primary_market} "
                f"fallback={fallback_market} verified={verified_count} live={live_count}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
