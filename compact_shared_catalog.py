import argparse
import json

from nationwide_platform.shared_catalog import backfill_all_shared_snapshots


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill shared reference snapshots for national market and cosmetics catalogs."
    )
    parser.add_argument(
        "--market-key",
        action="append",
        dest="market_keys",
        help="Optional market key filter. Can be provided multiple times.",
    )
    parser.add_argument(
        "--seed-city-plate",
        type=int,
        default=34,
        help="Preferred seed city plate code. Defaults to 34 (Istanbul).",
    )
    parser.add_argument(
        "--no-compact",
        action="store_true",
        help="Create shared snapshot mappings without deleting materialized offer/raw duplicates.",
    )
    args = parser.parse_args()

    result = backfill_all_shared_snapshots(
        market_keys=args.market_keys,
        preferred_city_plate_code=args.seed_city_plate,
        compact_materialized_offers=not args.no_compact,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
