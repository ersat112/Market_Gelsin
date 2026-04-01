import argparse

from nationwide_platform.rollout_runner import run_all_cities_controlled_flow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="81 il icin kontrollu canli akis planina gore toplu veri cekimi yapar."
    )
    parser.add_argument(
        "--only-stage",
        choices=(
            "live_controlled_local",
            "verified_local_needs_adapter",
            "discovery_pending_national_fallback",
        ),
        dest="only_stage",
        help="Yalnizca belirtilen rollout asamasindaki sehirleri kos.",
    )
    parser.add_argument(
        "--from-city",
        dest="from_city",
        help="Belirtilen city slug'dan itibaren devam et. Ornek: kocaeli",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="En fazla belirtilen sayida sehir icin kos.",
    )
    parser.add_argument(
        "--include-secondary-live",
        action="store_true",
        help="Primary marketten sonra live fallback marketi de kos.",
    )
    parser.add_argument(
        "--include-national-live",
        action="store_true",
        help="Her sehre ek olarak canli ulusal marketleri de kos.",
    )
    parser.add_argument(
        "--skip-fresh-hours",
        type=float,
        default=0,
        help="Son N saat icinde basarili kosu varsa ayni sehir-market run'ini atla.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Bir market run fail olursa komutu durdur.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_all_cities_controlled_flow(
        stage_filter=args.only_stage,
        from_city_slug=args.from_city,
        limit=args.limit,
        include_secondary_live=args.include_secondary_live,
        include_national_live=args.include_national_live,
        skip_fresh_hours=args.skip_fresh_hours,
        stop_on_error=args.stop_on_error,
    )

    print("81 Il Kontrollu Toplu Veri Akisi")
    print(f"- city_count: {summary['city_count']}")
    print(f"- executed_run_count: {summary['executed_run_count']}")
    print(f"- success_count: {summary['success_count']}")
    print(f"- failure_count: {summary['failure_count']}")
    print(f"- skipped_count: {summary['skipped_count']}")
    print(f"- total_fetched_count: {summary['total_fetched_count']}")
    print(f"- total_stored_count: {summary['total_stored_count']}")
    print()

    for result in summary["results"]:
        selected_markets = result["selected_markets"]
        if not selected_markets:
            print(
                f"- {result['city_name']} ({result['city_slug']}): "
                f"{result['status']} source=-"
            )
            continue
        market_fragments = []
        for market in selected_markets:
            fragment = f"{market['market_key']}:{market['status']}"
            if "stored_count" in market:
                fragment += f":stored={market['stored_count']}"
            market_fragments.append(fragment)
        print(
            f"- {result['city_name']} ({result['city_slug']}): "
            f"{result['status']} source={', '.join(market_fragments)}"
        )

    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
