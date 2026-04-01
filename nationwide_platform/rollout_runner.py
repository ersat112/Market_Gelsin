from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from .adapter_backlog import build_adapter_readiness
from .bootstrap import bootstrap_database
from .cities import CITIES, CITY_BY_SLUG, City
from .city_rollout import CityControlledFlowPlan, build_city_controlled_flow_plans
from .runner import run_market_collection
from .storage import connect


SUCCESSFUL_RUN_STATUSES = ("completed", "completed_with_errors")
NATIONAL_LIVE_SUPPLEMENTS = ("tarim_kredi_koop_market", "bizim_toptan_online")


@dataclass(frozen=True)
class CityCollectionJob:
    city_plate_code: int
    city_name: str
    city_slug: str
    rollout_stage: str
    primary_market_key: Optional[str]
    fallback_market_key: Optional[str]
    selected_markets: Tuple[Tuple[str, str], ...]


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _hours_ago_iso(hours: float) -> str:
    threshold = datetime.utcnow() - timedelta(hours=hours)
    return threshold.replace(microsecond=0).isoformat() + "Z"


def _city_by_plate_code() -> Dict[int, City]:
    return {city.plate_code: city for city in CITIES}


def _live_market_keys() -> set:
    return {
        row.market_key
        for row in build_adapter_readiness()
        if row.adapter_status == "live"
    }


def _select_markets_for_plan(
    plan: CityControlledFlowPlan,
    live_market_keys: set,
    include_secondary_live: bool,
    include_national_live: bool,
) -> Tuple[Tuple[str, str], ...]:
    selected: List[Tuple[str, str]] = []
    seen_keys = set()

    for source, market_key in (
        ("primary", plan.primary_market_key),
        ("fallback", plan.fallback_market_key),
    ):
        if not market_key or market_key not in live_market_keys or market_key in seen_keys:
            continue
        if source == "fallback" and not include_secondary_live and selected:
            continue
        selected.append((source, market_key))
        seen_keys.add(market_key)

    if include_national_live:
        for market_key in NATIONAL_LIVE_SUPPLEMENTS:
            if market_key in live_market_keys and market_key not in seen_keys:
                selected.append(("national_live", market_key))
                seen_keys.add(market_key)

    return tuple(selected)


def build_city_collection_jobs(
    stage_filter: Optional[str] = None,
    from_city_slug: Optional[str] = None,
    limit: Optional[int] = None,
    include_secondary_live: bool = False,
    include_national_live: bool = False,
    city_slugs: Optional[Sequence[str]] = None,
) -> List[CityCollectionJob]:
    city_by_plate = _city_by_plate_code()
    live_market_keys = _live_market_keys()
    jobs: List[CityCollectionJob] = []
    start_collecting = from_city_slug is None
    city_slug_set = set(city_slugs or [])

    for plan in build_city_controlled_flow_plans():
        city = city_by_plate[plan.city_plate_code]
        if city_slug_set and city.slug not in city_slug_set:
            continue
        if not start_collecting:
            if city.slug != from_city_slug:
                continue
            start_collecting = True

        if stage_filter and plan.rollout_stage != stage_filter:
            continue

        jobs.append(
            CityCollectionJob(
                city_plate_code=city.plate_code,
                city_name=city.name,
                city_slug=city.slug,
                rollout_stage=plan.rollout_stage,
                primary_market_key=plan.primary_market_key,
                fallback_market_key=plan.fallback_market_key,
                selected_markets=_select_markets_for_plan(
                    plan=plan,
                    live_market_keys=live_market_keys,
                    include_secondary_live=include_secondary_live,
                    include_national_live=include_national_live,
                ),
            )
        )
        if limit is not None and len(jobs) >= limit:
            break

    return jobs


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


def run_all_cities_controlled_flow(
    stage_filter: Optional[str] = None,
    from_city_slug: Optional[str] = None,
    limit: Optional[int] = None,
    include_secondary_live: bool = False,
    include_national_live: bool = False,
    city_slugs: Optional[Sequence[str]] = None,
    skip_fresh_hours: float = 0,
    stop_on_error: bool = False,
) -> dict:
    bootstrap_database()
    jobs = build_city_collection_jobs(
        stage_filter=stage_filter,
        from_city_slug=from_city_slug,
        limit=limit,
        include_secondary_live=include_secondary_live,
        include_national_live=include_national_live,
        city_slugs=city_slugs,
    )

    summary = {
        "started_at": _utc_now_iso(),
        "job_count": len(jobs),
        "city_count": len(jobs),
        "executed_run_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "skipped_count": 0,
        "total_fetched_count": 0,
        "total_stored_count": 0,
        "results": [],
    }

    with connect() as connection:
        for job in jobs:
            if not job.selected_markets:
                summary["skipped_count"] += 1
                summary["results"].append(
                    {
                        "city_slug": job.city_slug,
                        "city_name": job.city_name,
                        "rollout_stage": job.rollout_stage,
                        "status": "skipped_no_live_market",
                        "selected_markets": [],
                    }
                )
                continue

            city_result = {
                "city_slug": job.city_slug,
                "city_name": job.city_name,
                "rollout_stage": job.rollout_stage,
                "status": "completed",
                "selected_markets": [],
            }
            had_failure = False
            executed_any = False

            for source, market_key in job.selected_markets:
                if _has_fresh_successful_run(connection, market_key, job.city_plate_code, skip_fresh_hours):
                    summary["skipped_count"] += 1
                    city_result["selected_markets"].append(
                        {
                            "market_key": market_key,
                            "selection_source": source,
                            "status": "skipped_fresh",
                        }
                    )
                    continue

                executed_any = True
                try:
                    result = run_market_collection(
                        market_key=market_key,
                        city_slug=job.city_slug,
                        bootstrap=False,
                    )
                    summary["executed_run_count"] += 1
                    summary["total_fetched_count"] += result["fetched_count"]
                    summary["total_stored_count"] += result["stored_count"]
                    city_result["selected_markets"].append(
                        {
                            "market_key": market_key,
                            "selection_source": source,
                            "status": result["status"],
                            "run_id": result["run_id"],
                            "fetched_count": result["fetched_count"],
                            "stored_count": result["stored_count"],
                            "error_count": result["error_count"],
                        }
                    )
                except Exception as exc:
                    had_failure = True
                    summary["failure_count"] += 1
                    city_result["status"] = "completed_with_errors"
                    city_result["selected_markets"].append(
                        {
                            "market_key": market_key,
                            "selection_source": source,
                            "status": "failed",
                            "error": str(exc)[:500],
                        }
                    )
                    if stop_on_error:
                        summary["results"].append(city_result)
                        summary["finished_at"] = _utc_now_iso()
                        raise

            if executed_any and not had_failure:
                summary["success_count"] += 1
            elif not executed_any:
                city_result["status"] = "skipped_all"

            summary["results"].append(city_result)

    summary["finished_at"] = _utc_now_iso()
    return summary
