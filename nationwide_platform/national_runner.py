from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from .bootstrap import bootstrap_database
from .cities import CITY_BY_SLUG
from .national_priority import build_national_market_priorities
from .planner import CrawlTarget, build_default_targets
from .runner import clone_market_collection_from_seed, run_market_collection
from .shared_catalog import SHARED_REFERENCE_MARKETS
from .storage import connect


SUCCESSFUL_RUN_STATUSES = ("completed", "completed_with_errors")
SHARED_CATALOG_MARKETS = set(SHARED_REFERENCE_MARKETS)


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _hours_ago_iso(hours: float) -> str:
    threshold = datetime.utcnow() - timedelta(hours=hours)
    return threshold.replace(microsecond=0).isoformat() + "Z"


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


CITY_BY_PLATE = {city.plate_code: city for city in CITY_BY_SLUG.values()}
CITY_BY_PLATE_SLUG = {city.plate_code: city.slug for city in CITY_BY_SLUG.values()}


def _targets_by_market(
    city_filter: Optional[str] = None,
    city_limit: Optional[int] = None,
) -> Dict[str, List[CrawlTarget]]:
    filtered_targets: Dict[str, List[CrawlTarget]] = {}
    for target in build_default_targets():
        city = CITY_BY_PLATE.get(target.city_plate_code)
        city_slug = city.slug if city is not None else None
        if city_filter and city_slug != city_filter:
            continue
        filtered_targets.setdefault(target.market_key, []).append(target)

    for market_key, targets in filtered_targets.items():
        targets.sort(key=lambda row: (-row.priority_score, row.city_plate_code))
        if city_limit is not None:
            filtered_targets[market_key] = targets[:city_limit]
    return filtered_targets


def run_all_national_market_collection(
    only_live: bool = True,
    from_market_key: Optional[str] = None,
    market_limit: Optional[int] = None,
    city_filter: Optional[str] = None,
    city_limit: Optional[int] = None,
    only_market_keys: Optional[Sequence[str]] = None,
    skip_fresh_hours: float = 0,
    stop_on_error: bool = False,
) -> dict:
    bootstrap_database()
    priorities = build_national_market_priorities()
    targets_by_market = _targets_by_market(city_filter=city_filter, city_limit=city_limit)
    start_collecting = from_market_key is None
    only_market_key_set = set(only_market_keys or [])

    summary = {
        "started_at": _utc_now_iso(),
        "market_count": 0,
        "executed_market_count": 0,
        "planned_market_count": 0,
        "executed_run_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "skipped_count": 0,
        "total_fetched_count": 0,
        "total_stored_count": 0,
        "results": [],
    }

    with connect() as connection:
        for priority in priorities:
            if only_market_key_set and priority.market_key not in only_market_key_set:
                continue
            if not start_collecting:
                if priority.market_key != from_market_key:
                    continue
                start_collecting = True

            if only_live and priority.adapter_status != "live":
                summary["planned_market_count"] += 1
                summary["results"].append(
                    {
                        "market_key": priority.market_key,
                        "market_name": priority.market_name,
                        "priority_rank": priority.priority_rank,
                        "adapter_status": priority.adapter_status,
                        "status": "planned_adapter",
                        "target_count": priority.city_target_count,
                        "executed_runs": 0,
                        "stored_count": 0,
                    }
                )
                if market_limit is not None and len(summary["results"]) >= market_limit:
                    break
                continue

            market_targets = targets_by_market.get(priority.market_key, [])
            market_result = {
                "market_key": priority.market_key,
                "market_name": priority.market_name,
                "priority_rank": priority.priority_rank,
                "adapter_status": priority.adapter_status,
                "status": "completed",
                "target_count": len(market_targets),
                "executed_runs": 0,
                "stored_count": 0,
                "city_results": [],
            }
            summary["market_count"] += 1
            had_failure = False
            pending_targets: List[CrawlTarget] = []

            for target in market_targets:
                if _has_fresh_successful_run(connection, priority.market_key, target.city_plate_code, skip_fresh_hours):
                    summary["skipped_count"] += 1
                    market_result["city_results"].append(
                        {
                            "city_name": target.city_name,
                            "status": "skipped_fresh",
                        }
                    )
                    continue
                pending_targets.append(target)

            seed_result = None
            seed_target = pending_targets[0] if pending_targets else None
            if priority.market_key in SHARED_CATALOG_MARKETS and seed_target is not None:
                try:
                    seed_result = run_market_collection(
                        market_key=priority.market_key,
                        city_slug=CITY_BY_PLATE_SLUG[seed_target.city_plate_code],
                        bootstrap=False,
                    )
                except Exception as exc:
                    had_failure = True
                    summary["failure_count"] += 1
                    market_result["status"] = "completed_with_errors"
                    market_result["city_results"].append(
                        {
                            "city_name": seed_target.city_name,
                            "status": "failed_shared_fetch",
                            "error": str(exc)[:500],
                        }
                    )
                    if stop_on_error:
                        summary["results"].append(market_result)
                        summary["finished_at"] = _utc_now_iso()
                        raise
                    summary["results"].append(market_result)
                    if market_limit is not None and len(summary["results"]) >= market_limit:
                        break
                    continue

            for target in pending_targets:
                try:
                    if seed_result is not None and seed_target is not None:
                        if target.city_plate_code == seed_target.city_plate_code:
                            result = seed_result
                        else:
                            result = clone_market_collection_from_seed(
                                seed_run_id=seed_result["run_id"],
                                market_key=priority.market_key,
                                city_slug=CITY_BY_PLATE_SLUG[target.city_plate_code],
                                address_label=f"shared_catalog_seed:{seed_target.city_name}",
                                bootstrap=False,
                            )
                    else:
                        result = run_market_collection(
                            market_key=priority.market_key,
                            city_slug=CITY_BY_PLATE_SLUG[target.city_plate_code],
                            bootstrap=False,
                        )
                    summary["executed_run_count"] += 1
                    summary["total_fetched_count"] += result["fetched_count"]
                    summary["total_stored_count"] += result["stored_count"]
                    market_result["executed_runs"] += 1
                    market_result["stored_count"] += result["stored_count"]
                    market_result["city_results"].append(
                        {
                            "city_name": target.city_name,
                            "status": result["status"],
                            "stored_count": result["stored_count"],
                            "run_id": result["run_id"],
                        }
                    )
                except Exception as exc:
                    had_failure = True
                    summary["failure_count"] += 1
                    market_result["status"] = "completed_with_errors"
                    market_result["city_results"].append(
                        {
                            "city_name": target.city_name,
                            "status": "failed",
                            "error": str(exc)[:500],
                        }
                    )
                    if stop_on_error:
                        summary["results"].append(market_result)
                        summary["finished_at"] = _utc_now_iso()
                        raise

            if market_result["executed_runs"] > 0 and not had_failure:
                summary["success_count"] += 1
                summary["executed_market_count"] += 1
            elif market_result["executed_runs"] == 0 and market_result["target_count"] == 0:
                market_result["status"] = "no_targets"

            summary["results"].append(market_result)
            if market_limit is not None and len(summary["results"]) >= market_limit:
                break

    summary["finished_at"] = _utc_now_iso()
    return summary
