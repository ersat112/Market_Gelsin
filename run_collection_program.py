import argparse

from nationwide_platform.program_runner import run_collection_program


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="V1/V2 kapsam programina gore haftalik full veya hot-scan refresh kosusu planlar."
    )
    parser.add_argument(
        "--lane",
        choices=("weekly_full", "hot_scan"),
        default="weekly_full",
        help="Haftalik tum katalog yenilemesi veya 48 saat hot urun yenilemesi.",
    )
    parser.add_argument(
        "--scope",
        choices=("v1", "v2", "all"),
        default="v1",
        help="V1 cekirdek + buyuksehir yerelleri, V2 kalan iller veya tum program.",
    )
    parser.add_argument(
        "--skip-fresh-hours",
        type=float,
        default=0,
        help="Son N saat icinde basarili kosu varsa ayni hedefi atla.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Komutu sadece plan ozeti olarak calistir, gercek crawl baslatma.",
    )
    parser.add_argument(
        "--hot-limit",
        type=int,
        default=500,
        help="Hot scan queue icin en fazla aday sayisi.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Bir run hata verirse tum programi durdur.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_collection_program(
        lane=args.lane,
        scope=args.scope,
        skip_fresh_hours=args.skip_fresh_hours,
        dry_run=args.dry_run,
        hot_limit=args.hot_limit,
        stop_on_error=args.stop_on_error,
    )
    print("Veri Toplama Programi")
    print(f"- lane: {summary['lane']}")
    print(f"- scope: {summary['scope']}")
    print(f"- full_refresh_hours: {summary['full_refresh_hours']}")
    print(f"- hot_refresh_hours: {summary['hot_refresh_hours']}")
    print(f"- dry_run: {summary['dry_run']}")
    if "national_market_keys" in summary:
        print(f"- national_market_count: {len(summary['national_market_keys'])}")
        print(f"- metro_city_count: {len(summary['metro_city_slugs'])}")
        print(f"- remaining_city_count: {len(summary['remaining_city_slugs'])}")
    if "candidate_count" in summary:
        print(f"- candidate_count: {summary['candidate_count']}")
        print(f"- market_city_job_count: {summary['market_city_job_count']}")
        print(f"- executed_run_count: {summary['executed_run_count']}")
    if "notes" in summary:
        print(f"- notes: {summary['notes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
