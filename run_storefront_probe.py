import argparse

from nationwide_platform.bootstrap import bootstrap_database
from nationwide_platform.storage import connect, initialize_schema, upsert_market_storefront_probes
from nationwide_platform.storefront_probe import probe_remaining_local_markets


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe remaining local market storefronts and store results.")
    parser.add_argument("--include-live", action="store_true", help="Probe live local adapters as well.")
    args = parser.parse_args()

    bootstrap_database()
    probes = probe_remaining_local_markets(include_live=args.include_live)
    with connect() as connection:
        initialize_schema(connection)
        upsert_market_storefront_probes(connection, probes)

    open_count = sum(1 for probe in probes if probe.product_flow_status == "open_product_flow")
    blocked_count = sum(1 for probe in probes if probe.product_flow_status == "blocked_challenge")
    print(f"Probed markets: {len(probes)}")
    print(f"Open product flow: {open_count}")
    print(f"Blocked challenge: {blocked_count}")
    for probe in probes:
        print(
            f"- {probe.market_key}: status={probe.product_flow_status}, "
            f"family={probe.storefront_family}, adapter={probe.recommended_adapter_family}, "
            f"sample_count={probe.sample_product_count}"
        )
        if probe.sample_url:
            print(f"  sample={probe.sample_url}")
        print(f"  notes={probe.notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
