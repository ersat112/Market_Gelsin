from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from .bootstrap import bootstrap_database
from .cities import CITIES, CITY_BY_SLUG
from .collection_program import HOT_PRODUCT_REFRESH_HOURS
from .runner import run_market_collection
from .storage import connect


SUCCESSFUL_RUN_STATUSES = ("completed", "completed_with_errors")
CITY_SLUG_BY_PLATE = {city.plate_code: city.slug for city in CITIES}


@dataclass(frozen=True)
class HotRefreshCandidate:
    barcode: str
    city_plate_code: int
    market_key: str
    scan_count: int
    matched_offer_count: int
    last_signal_at: str
    refresh_due_at: str
    priority_score: int
    notes: str


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _days_ago_iso(days: int) -> str:
    return (datetime.utcnow() - timedelta(days=days)).replace(microsecond=0).isoformat() + "Z"


def _hours_ago_iso(hours: float) -> str:
    return (datetime.utcnow() - timedelta(hours=hours)).replace(microsecond=0).isoformat() + "Z"


def upsert_scan_signal(
    connection,
    barcode: str,
    city_plate_code: int,
    signal_date: str,
    scan_count: int,
    source_app: str = "barkod_analiz",
) -> None:
    now = _utc_now_iso()
    connection.execute(
        """
        INSERT INTO barcode_scan_signals (
            barcode,
            city_plate_code,
            signal_date,
            scan_count,
            source_app,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(barcode, city_plate_code, signal_date, source_app) DO UPDATE SET
            scan_count = excluded.scan_count,
            updated_at = excluded.updated_at
        """,
        (barcode, city_plate_code, signal_date, scan_count, source_app, now, now),
    )
    connection.commit()


def rebuild_hot_refresh_candidates(
    connection,
    lookback_days: int = 14,
    min_scan_count: int = 3,
    limit: int = 500,
) -> List[HotRefreshCandidate]:
    cutoff = _days_ago_iso(lookback_days)
    rows = connection.execute(
        """
        WITH aggregated_signals AS (
            SELECT
                barcode,
                city_plate_code,
                SUM(scan_count) AS total_scan_count,
                MAX(signal_date) AS last_signal_at
            FROM barcode_scan_signals
            WHERE signal_date >= ?
            GROUP BY barcode, city_plate_code
            HAVING SUM(scan_count) >= ?
        ),
        matched_offers AS (
            SELECT
                s.barcode,
                CASE
                    WHEN s.city_plate_code = 0 THEN offers.city_plate_code
                    ELSE s.city_plate_code
                END AS city_plate_code,
                offers.market_key,
                s.total_scan_count,
                s.last_signal_at,
                COUNT(*) AS matched_offer_count
            FROM aggregated_signals s
            JOIN current_offers offers
                ON offers.source_barcode = s.barcode
               AND (s.city_plate_code = 0 OR offers.city_plate_code = s.city_plate_code)
            GROUP BY
                s.barcode,
                CASE
                    WHEN s.city_plate_code = 0 THEN offers.city_plate_code
                    ELSE s.city_plate_code
                END,
                offers.market_key,
                s.total_scan_count,
                s.last_signal_at
        )
        SELECT
            barcode,
            city_plate_code,
            market_key,
            total_scan_count,
            matched_offer_count,
            last_signal_at
        FROM matched_offers
        ORDER BY total_scan_count DESC, matched_offer_count DESC, market_key, city_plate_code
        LIMIT ?
        """,
        (cutoff, min_scan_count, max(1, limit)),
    ).fetchall()

    connection.execute("DELETE FROM hot_product_refresh_candidates")
    candidates: List[HotRefreshCandidate] = []
    now = _utc_now_iso()
    for barcode, city_plate_code, market_key, total_scan_count, matched_offer_count, last_signal_at in rows:
        priority_score = min(100, int(total_scan_count) + min(int(matched_offer_count), 25))
        notes = "BarkodAnaliz scan sinyaline gore 48 saatlik hot refresh adayi."
        candidate = HotRefreshCandidate(
            barcode=barcode,
            city_plate_code=int(city_plate_code),
            market_key=market_key,
            scan_count=int(total_scan_count),
            matched_offer_count=int(matched_offer_count),
            last_signal_at=last_signal_at,
            refresh_due_at=now,
            priority_score=priority_score,
            notes=notes,
        )
        candidates.append(candidate)
        connection.execute(
            """
            INSERT INTO hot_product_refresh_candidates (
                barcode,
                city_plate_code,
                market_key,
                scan_count,
                matched_offer_count,
                execution_mode,
                refresh_interval_hours,
                refresh_due_at,
                last_signal_at,
                priority_score,
                status,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'market_city_rerun', ?, ?, ?, ?, 'planned', ?, ?, ?)
            """,
            (
                candidate.barcode,
                candidate.city_plate_code,
                candidate.market_key,
                candidate.scan_count,
                candidate.matched_offer_count,
                HOT_PRODUCT_REFRESH_HOURS,
                candidate.refresh_due_at,
                candidate.last_signal_at,
                candidate.priority_score,
                candidate.notes,
                now,
                now,
            ),
        )
    connection.commit()
    return candidates


def run_hot_refresh_cycle(
    limit: int = 100,
    lookback_days: int = 14,
    min_scan_count: int = 3,
    skip_fresh_hours: float = 0,
    stop_on_error: bool = False,
) -> Dict[str, object]:
    bootstrap_database()
    summary: Dict[str, object] = {
        "started_at": _utc_now_iso(),
        "candidate_count": 0,
        "market_city_job_count": 0,
        "executed_run_count": 0,
        "skipped_count": 0,
        "failure_count": 0,
        "total_stored_count": 0,
        "results": [],
    }

    with connect() as connection:
        candidates = rebuild_hot_refresh_candidates(
            connection=connection,
            lookback_days=lookback_days,
            min_scan_count=min_scan_count,
            limit=limit,
        )
        summary["candidate_count"] = len(candidates)

        grouped: Dict[Tuple[str, int], List[HotRefreshCandidate]] = {}
        for candidate in candidates:
            grouped.setdefault((candidate.market_key, candidate.city_plate_code), []).append(candidate)
        summary["market_city_job_count"] = len(grouped)

        for (market_key, city_plate_code), grouped_candidates in grouped.items():
            city_slug = CITY_SLUG_BY_PLATE[city_plate_code]
            if _has_fresh_successful_run(connection, market_key, city_plate_code, skip_fresh_hours):
                summary["skipped_count"] += 1
                _update_candidate_status(connection, market_key, city_plate_code, "skipped_fresh")
                summary["results"].append(
                    {
                        "market_key": market_key,
                        "city_plate_code": city_plate_code,
                        "city_slug": city_slug,
                        "status": "skipped_fresh",
                        "barcodes": [candidate.barcode for candidate in grouped_candidates],
                    }
                )
                continue
            try:
                result = run_market_collection(market_key=market_key, city_slug=city_slug, bootstrap=False)
                summary["executed_run_count"] += 1
                summary["total_stored_count"] += result["stored_count"]
                _update_candidate_status(connection, market_key, city_plate_code, "completed")
                summary["results"].append(
                    {
                        "market_key": market_key,
                        "city_plate_code": city_plate_code,
                        "city_slug": city_slug,
                        "status": result["status"],
                        "stored_count": result["stored_count"],
                        "run_id": result["run_id"],
                        "barcodes": [candidate.barcode for candidate in grouped_candidates[:10]],
                    }
                )
            except Exception as exc:
                summary["failure_count"] += 1
                _update_candidate_status(connection, market_key, city_plate_code, "failed")
                summary["results"].append(
                    {
                        "market_key": market_key,
                        "city_plate_code": city_plate_code,
                        "city_slug": city_slug,
                        "status": "failed",
                        "error": str(exc)[:500],
                        "barcodes": [candidate.barcode for candidate in grouped_candidates[:10]],
                    }
                )
                if stop_on_error:
                    summary["finished_at"] = _utc_now_iso()
                    raise

    summary["finished_at"] = _utc_now_iso()
    return summary


def _has_fresh_successful_run(connection, market_key: str, city_plate_code: int, skip_fresh_hours: float) -> bool:
    if skip_fresh_hours <= 0:
        return False
    threshold = _hours_ago_iso(skip_fresh_hours)
    row = connection.execute(
        """
        SELECT 1
        FROM scrape_runs
        WHERE market_key = ?
          AND city_plate_code = ?
          AND status IN (?, ?)
          AND started_at >= ?
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (
            market_key,
            city_plate_code,
            SUCCESSFUL_RUN_STATUSES[0],
            SUCCESSFUL_RUN_STATUSES[1],
            threshold,
        ),
    ).fetchone()
    return row is not None


def _update_candidate_status(connection, market_key: str, city_plate_code: int, status: str) -> None:
    connection.execute(
        """
        UPDATE hot_product_refresh_candidates
        SET status = ?, updated_at = ?
        WHERE market_key = ? AND city_plate_code = ?
        """,
        (status, _utc_now_iso(), market_key, city_plate_code),
    )
    connection.commit()
