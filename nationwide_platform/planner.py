from dataclasses import dataclass
from typing import Dict, Iterable, List

from .cities import CITIES, City
from .market_registry import MARKET_SOURCES, MarketSource


@dataclass(frozen=True)
class CrawlTarget:
    market_key: str
    city_plate_code: int
    city_name: str
    priority_score: int
    requires_address_seed: bool
    probe_strategy: str
    refresh_hours: int
    notes: str


def _priority_for_market(market: MarketSource, city: City) -> int:
    base_priority = {
        "city_specific": 98,
        "district_cluster": 97,
        "district_or_city_specific": 96,
        "national_store_network": 95,
        "all_81_target": 90,
        "wide_national": 85,
        "selective_metro": 65,
    }.get(market.coverage_scope, 50)

    metro_bonus = 5 if city.slug in {"istanbul", "ankara", "izmir", "bursa", "antalya", "kocaeli"} else 0
    return base_priority + metro_bonus


def _probe_strategy(market: MarketSource) -> str:
    if market.requires_address_seed:
        return "city_probe_then_address_seed"
    return "city_level_category_probe"


def _supported_cities(market: MarketSource) -> Iterable[City]:
    if market.target_mode == "discovery_backlog":
        return []
    if market.supported_city_slugs:
        allowed = set(market.supported_city_slugs)
        return [city for city in CITIES if city.slug in allowed]
    return CITIES


def build_default_targets() -> List[CrawlTarget]:
    targets: List[CrawlTarget] = []
    for market in MARKET_SOURCES:
        for city in _supported_cities(market):
            targets.append(
                CrawlTarget(
                    market_key=market.key,
                    city_plate_code=city.plate_code,
                    city_name=city.name,
                    priority_score=_priority_for_market(market, city),
                    requires_address_seed=market.requires_address_seed,
                    probe_strategy=_probe_strategy(market),
                    refresh_hours=market.refresh_hours,
                    notes=f"{market.name} / {city.name} target",
                )
            )
    return targets


def summarize_targets(targets: List[CrawlTarget]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for target in targets:
        summary[target.market_key] = summary.get(target.market_key, 0) + 1
    return summary
