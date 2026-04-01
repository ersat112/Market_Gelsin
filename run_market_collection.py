import sys

from nationwide_platform.runner import run_market_collection


def main() -> int:
    if len(sys.argv) < 3:
        print("Kullanim: python3 run_market_collection.py <market_key> <city_slug> [address_label]")
        return 1

    market_key = sys.argv[1]
    city_slug = sys.argv[2]
    address_label = sys.argv[3] if len(sys.argv) > 3 else None

    result = run_market_collection(market_key=market_key, city_slug=city_slug, address_label=address_label)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
