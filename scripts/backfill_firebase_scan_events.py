import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nationwide_platform.barcode_ingest import backfill_existing_scan_events


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    result = backfill_existing_scan_events(limit=limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
