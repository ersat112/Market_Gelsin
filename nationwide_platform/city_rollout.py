from dataclasses import dataclass
from typing import Dict, List, Optional

from .adapter_backlog import IMPLEMENTED_MARKETS, build_adapter_readiness
from .cities import CITIES, City
from .market_registry import MARKET_SOURCES, MarketSource


@dataclass(frozen=True)
class CityControlledFlowPlan:
    city_plate_code: int
    rollout_stage: str
    collection_mode: str
    primary_market_key: Optional[str]
    fallback_market_key: Optional[str]
    verified_market_count: int
    live_market_count: int
    next_step: str
    notes: str


FALLBACK_MARKET_KEYS = ("cepte_sok", "migros_sanal_market")


def build_city_controlled_flow_plans() -> List[CityControlledFlowPlan]:
    readiness_by_key = {row.market_key: row for row in build_adapter_readiness()}
    market_by_key = {market.key: market for market in MARKET_SOURCES}
    fallback_markets = [
        market_by_key[market_key]
        for market_key in FALLBACK_MARKET_KEYS
        if market_key in IMPLEMENTED_MARKETS and market_key in market_by_key
    ]

    plans: List[CityControlledFlowPlan] = []
    for city in CITIES:
        city_markets = _city_specific_markets(city, readiness_by_key)
        local_live_markets = [market for market in city_markets if market.key in IMPLEMENTED_MARKETS]

        if local_live_markets:
            primary_market = local_live_markets[0]
            fallback_market = _choose_fallback(city_markets[1:], fallback_markets, exclude={primary_market.key})
            plans.append(
                CityControlledFlowPlan(
                    city_plate_code=city.plate_code,
                    rollout_stage="live_controlled_local",
                    collection_mode="controlled_sample",
                    primary_market_key=primary_market.key,
                    fallback_market_key=fallback_market.key if fallback_market else None,
                    verified_market_count=len(city_markets),
                    live_market_count=len(local_live_markets),
                    next_step="Kontrollu akisi periyodiklestir, sonra kategori ve sayfa kapsamini artir.",
                    notes=(
                        f"{city.name} icin en az bir yerel market adapteri canli. "
                        f"Tam katalog oncesi ayni sehirde ikinci market veya fallback baglanmali."
                    ),
                )
            )
            continue

        if city_markets:
            primary_market = city_markets[0]
            fallback_market = _choose_fallback([], fallback_markets, exclude={primary_market.key})
            plans.append(
                CityControlledFlowPlan(
                    city_plate_code=city.plate_code,
                    rollout_stage="verified_local_needs_adapter",
                    collection_mode="controlled_sample",
                    primary_market_key=primary_market.key,
                    fallback_market_key=fallback_market.key if fallback_market else None,
                    verified_market_count=len(city_markets),
                    live_market_count=0,
                    next_step="Bu sehir icin once kontrollu ornekleme adapteri yaz, sonra ilk run al.",
                    notes=(
                        f"{city.name} icin dogrulanmis yerel kaynak var ancak canli adapter eksik. "
                        f"Ilk hedef kontrollu veri akisidir; tam katalog ikinci fazdir."
                    ),
                )
            )
            continue

        primary_market = fallback_markets[0] if fallback_markets else None
        secondary_market = fallback_markets[1] if len(fallback_markets) > 1 else None
        plans.append(
            CityControlledFlowPlan(
                city_plate_code=city.plate_code,
                rollout_stage="discovery_pending_national_fallback",
                collection_mode="controlled_sample",
                primary_market_key=primary_market.key if primary_market else None,
                fallback_market_key=secondary_market.key if secondary_market else None,
                verified_market_count=0,
                live_market_count=0,
                next_step="Yerel market kesfi surerken ulusal fallback ile kontrollu akis ac.",
                notes=(
                    f"{city.name} icin yerel kaynak kesfi tamamlanmadi. "
                    f"Faz 1 icin ulusal fallback, faz 2 icin yerel market kesfi ve adapter gerekir."
                ),
            )
        )
    return plans


def summarize_city_controlled_flow_plans(plans: Optional[List[CityControlledFlowPlan]] = None) -> Dict[str, int]:
    resolved_plans = plans or build_city_controlled_flow_plans()
    summary: Dict[str, int] = {}
    for plan in resolved_plans:
        summary[plan.rollout_stage] = summary.get(plan.rollout_stage, 0) + 1
    return summary


def _city_specific_markets(city: City, readiness_by_key: Dict[str, object]) -> List[MarketSource]:
    city_markets = [
        market
        for market in MARKET_SOURCES
        if market.supported_city_slugs and city.slug in market.supported_city_slugs
    ]
    city_markets.sort(
        key=lambda market: (
            0 if market.key in IMPLEMENTED_MARKETS else 1,
            0 if not market.requires_address_seed else 1,
            -getattr(readiness_by_key.get(market.key), "priority_score", 0),
            market.name,
        )
    )
    return city_markets


def _choose_fallback(
    city_markets: List[MarketSource],
    fallback_markets: List[MarketSource],
    exclude: set,
) -> Optional[MarketSource]:
    for market in city_markets:
        if market.key not in exclude:
            return market
    for market in fallback_markets:
        if market.key not in exclude:
            return market
    return None
