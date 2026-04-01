import json
import os
import sys
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nationwide_platform.env_loader import load_local_env_files


SQL_PATH = ROOT / "supabase_mg_read_model.sql"


def _db_url() -> str:
    for key in ("MARKET_GELSIN_DB_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise SystemExit("MARKET_GELSIN_DB_URL or DATABASE_URL is required")


def _execute_sql_script(connection, script: str) -> None:
    statements = [part.strip() for part in script.split(";") if part.strip()]
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def main() -> int:
    load_local_env_files()
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    with psycopg.connect(_db_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET statement_timeout TO 0")
        _execute_sql_script(connection, sql_text)
        connection.commit()
        with connection.cursor() as cursor:
            cursor.execute("select count(*) from mg_products")
            mg_products = cursor.fetchone()[0]
            cursor.execute("select count(*) from mg_markets")
            mg_markets = cursor.fetchone()[0]
            cursor.execute("select count(*) from mg_market_offers")
            mg_market_offers = cursor.fetchone()[0]
            cursor.execute("select count(*) from mg_price_history")
            mg_price_history = cursor.fetchone()[0]
            cursor.execute("select count(*) from mg_product_city_summary")
            mg_product_city_summary = cursor.fetchone()[0]
            cursor.execute("select count(*) from mg_product_best_offers")
            mg_product_best_offers = cursor.fetchone()[0]
            cursor.execute("select count(*) from mg_product_price_trends")
            mg_product_price_trends = cursor.fetchone()[0]

    print(
        json.dumps(
            {
                "ok": True,
                "sql_path": str(SQL_PATH),
                "counts": {
                    "mg_products": mg_products,
                    "mg_markets": mg_markets,
                    "mg_market_offers": mg_market_offers,
                    "mg_price_history": mg_price_history,
                    "mg_product_city_summary": mg_product_city_summary,
                    "mg_product_best_offers": mg_product_best_offers,
                    "mg_product_price_trends": mg_product_price_trends,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
