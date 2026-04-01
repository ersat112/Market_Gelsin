from typing import Dict, Optional, Sequence

from .collection_program import (
    HOT_PRODUCT_REFRESH_HOURS,
    V1_NATIONAL_CORE_MARKET_KEYS,
    WEEKLY_FULL_REFRESH_HOURS,
    metropolitan_city_slugs,
    remaining_city_slugs,
)
from .hot_refresh import run_hot_refresh_cycle
from .national_runner import run_all_national_market_collection
from .rollout_runner import run_all_cities_controlled_flow


def run_collection_program(
    lane: str = "weekly_full",
    scope: str = "v1",
    skip_fresh_hours: float = 0,
    dry_run: bool = False,
    hot_limit: int = 500,
    stop_on_error: bool = False,
) -> Dict[str, object]:
    if lane not in {"weekly_full", "hot_scan"}:
        raise ValueError("invalid_lane")
    if scope not in {"v1", "v2", "all"}:
        raise ValueError("invalid_scope")

    if lane == "hot_scan":
        if dry_run:
            return {
                "lane": lane,
                "scope": scope,
                "full_refresh_hours": WEEKLY_FULL_REFRESH_HOURS,
                "hot_refresh_hours": HOT_PRODUCT_REFRESH_HOURS,
                "dry_run": True,
                "notes": "Hot scan refresh dry-run; queue rebuild and execution skipped.",
            }
        return run_hot_refresh_cycle(
            limit=hot_limit,
            skip_fresh_hours=skip_fresh_hours,
            stop_on_error=stop_on_error,
        )

    national_keys = tuple(V1_NATIONAL_CORE_MARKET_KEYS) if scope in {"v1", "all"} else tuple()
    metro_slugs = metropolitan_city_slugs() if scope in {"v1", "all"} else tuple()
    remaining_slugs = remaining_city_slugs() if scope in {"v2", "all"} else tuple()

    summary: Dict[str, object] = {
        "lane": lane,
        "scope": scope,
        "full_refresh_hours": WEEKLY_FULL_REFRESH_HOURS,
        "hot_refresh_hours": HOT_PRODUCT_REFRESH_HOURS,
        "dry_run": dry_run,
        "national_market_keys": list(national_keys),
        "metro_city_slugs": list(metro_slugs),
        "remaining_city_slugs": list(remaining_slugs),
    }
    if dry_run:
        summary["notes"] = "Weekly full refresh dry-run; market and city scopes were planned but not executed."
        return summary

    if national_keys:
        summary["national"] = run_all_national_market_collection(
            only_live=True,
            only_market_keys=national_keys,
            skip_fresh_hours=skip_fresh_hours,
            stop_on_error=stop_on_error,
        )
    if metro_slugs:
        summary["metro_local"] = run_all_cities_controlled_flow(
            city_slugs=metro_slugs,
            include_secondary_live=True,
            include_national_live=False,
            skip_fresh_hours=skip_fresh_hours,
            stop_on_error=stop_on_error,
        )
    if remaining_slugs:
        summary["remaining_local"] = run_all_cities_controlled_flow(
            city_slugs=remaining_slugs,
            include_secondary_live=False,
            include_national_live=False,
            skip_fresh_hours=skip_fresh_hours,
            stop_on_error=stop_on_error,
        )
    return summary
