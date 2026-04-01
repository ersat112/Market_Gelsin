import json
import os
import sys
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nationwide_platform.env_loader import load_local_env_files


load_local_env_files()


def _db_url() -> str:
    for key in ("MARKET_GELSIN_DB_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise SystemExit("MARKET_GELSIN_DB_URL or DATABASE_URL is required")


def main() -> int:
    with psycopg.connect(_db_url(), connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database(),
                    current_user,
                    inet_server_addr()::text,
                    inet_server_port(),
                    version()
                """
            )
            row = cursor.fetchone()
    print(
        json.dumps(
            {
                "ok": True,
                "database": row[0],
                "user": row[1],
                "host": row[2],
                "port": row[3],
                "version": row[4],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
