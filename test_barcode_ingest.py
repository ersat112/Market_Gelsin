import tempfile
import unittest
from pathlib import Path

from nationwide_platform.barcode_ingest import ingest_barcode_scan_payload
from nationwide_platform.storage import connect


class BarcodeIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "barcode_ingest_test.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_single_event_is_stored_and_aggregated(self) -> None:
        result = ingest_barcode_scan_payload(
            {
                "barcode": "8690000000001",
                "city_code": "34",
                "scanned_at": "2026-04-01T10:15:00Z",
                "scan_count": 2,
                "device_id": "android-01",
            },
            db_path=self.db_path,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["received_count"], 1)
        self.assertEqual(result["ingested_count"], 1)
        self.assertEqual(result["duplicate_count"], 0)

        with connect(self.db_path) as connection:
            event_row = connection.execute(
                """
                SELECT barcode, city_plate_code, signal_date, scan_count
                FROM barcode_scan_events
                """
            ).fetchone()
            signal_row = connection.execute(
                """
                SELECT barcode, city_plate_code, signal_date, scan_count
                FROM barcode_scan_signals
                """
            ).fetchone()

        self.assertEqual(event_row, ("8690000000001", 34, "2026-04-01", 2))
        self.assertEqual(signal_row, ("8690000000001", 34, "2026-04-01", 2))

    def test_duplicate_event_is_ignored_and_does_not_increment_signal(self) -> None:
        payload = {
            "barcode": "8690000000002",
            "city_code": "06",
            "scanned_at": "2026-04-01T11:00:00Z",
            "device_id": "android-02",
            "session_id": "session-1",
        }

        first = ingest_barcode_scan_payload(payload, db_path=self.db_path)
        second = ingest_barcode_scan_payload(payload, db_path=self.db_path)

        self.assertEqual(first["ingested_count"], 1)
        self.assertEqual(second["ingested_count"], 0)
        self.assertEqual(second["duplicate_count"], 1)

        with connect(self.db_path) as connection:
            counts = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM barcode_scan_events),
                    (SELECT COUNT(*) FROM barcode_scan_signals),
                    (SELECT scan_count FROM barcode_scan_signals LIMIT 1)
                """
            ).fetchone()

        self.assertEqual(counts, (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
