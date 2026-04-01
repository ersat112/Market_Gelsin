from pprint import pprint

from nationwide_platform.api_service import get_collection_program_status


def main() -> int:
    pprint(get_collection_program_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
