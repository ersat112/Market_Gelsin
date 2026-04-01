import argparse

from nationwide_platform.national_runner import run_all_national_market_collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ulusal market onceligine gore toplu veri cekimi yapar."
    )
    parser.add_argument(
        "--include-planned",
        action="store_true",
        help="Canli olmayan ama oncelik listesinde bulunan marketleri de ozete dahil et.",
    )
    parser.add_argument(
        "--from-market",
        dest="from_market",
        help="Belirtilen market_key'den itibaren devam et.",
    )
    parser.add_argument(
        "--market-limit",
        type=int,
        help="En fazla belirtilen sayida market satiri islenir.",
    )
    parser.add_argument(
        "--city",
        dest="city_slug",
        help="Yalnizca tek bir sehir icin kos. Ornek: istanbul",
    )
    parser.add_argument(
        "--city-limit",
        type=int,
        help="Her market icin en fazla belirtilen sayida sehir hedefi kosulur.",
    )
    parser.add_argument(
        "--skip-fresh-hours",
        type=float,
        default=0,
        help="Son N saat icinde basarili kosu varsa ayni market-sehir run'ini atla.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Bir market run fail olursa komutu durdur.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_all_national_market_collection(
        only_live=not args.include_planned,
        from_market_key=args.from_market,
        market_limit=args.market_limit,
        city_filter=args.city_slug,
        city_limit=args.city_limit,
        skip_fresh_hours=args.skip_fresh_hours,
        stop_on_error=args.stop_on_error,
    )

    print("Ulusal Market Toplu Veri Akisi")
    print(f"- market_count: {summary['market_count']}")
    print(f"- executed_market_count: {summary['executed_market_count']}")
    print(f"- planned_market_count: {summary['planned_market_count']}")
    print(f"- executed_run_count: {summary['executed_run_count']}")
    print(f"- success_count: {summary['success_count']}")
    print(f"- failure_count: {summary['failure_count']}")
    print(f"- skipped_count: {summary['skipped_count']}")
    print(f"- total_fetched_count: {summary['total_fetched_count']}")
    print(f"- total_stored_count: {summary['total_stored_count']}")
    print()

    for result in summary["results"]:
        print(
            f"- #{result['priority_rank']} {result['market_name']} ({result['market_key']}): "
            f"{result['status']} adapter={result['adapter_status']} "
            f"targets={result['target_count']} executed={result['executed_runs']} stored={result['stored_count']}"
        )

    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
