from nationwide_platform.national_priority import build_national_market_priorities


def main() -> int:
    rows = build_national_market_priorities()
    print("Ulusal Market Oncelik Listesi")
    for row in rows:
        print(
            f"- #{row.priority_rank} {row.market_name} ({row.market_key}) | "
            f"adapter={row.adapter_status} | family={row.adapter_family} | "
            f"targets={row.city_target_count} | scope={row.coverage_scope}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
