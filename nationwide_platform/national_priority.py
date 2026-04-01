from dataclasses import dataclass
from typing import Dict, List, Tuple

from .adapter_backlog import AdapterReadiness, build_adapter_readiness
from .market_registry import MARKET_BY_KEY, MarketSource


CORE_NATIONAL_MARKET_ORDER: Tuple[str, ...] = (
    "bim_market",
    "a101_kapida",
    "cepte_sok",
    "migros_sanal_market",
    "carrefoursa_online_market",
    "tarim_kredi_koop_market",
    "bizim_toptan_online",
    "getir_buyuk",
)

NATIONAL_COVERAGE_SCOPES = {
    "national_store_network",
    "wide_national",
    "all_81_target",
}


@dataclass(frozen=True)
class NationalMarketPriority:
    priority_rank: int
    market_key: str
    market_name: str
    coverage_scope: str
    crawl_strategy: str
    adapter_status: str
    adapter_family: str
    city_target_count: int
    priority_score: int
    official_notes: str


def _is_national_market(market: MarketSource) -> bool:
    return market.key in CORE_NATIONAL_MARKET_ORDER or market.coverage_scope in NATIONAL_COVERAGE_SCOPES


def build_national_market_priorities() -> List[NationalMarketPriority]:
    readiness_by_key: Dict[str, AdapterReadiness] = {
        row.market_key: row
        for row in build_adapter_readiness()
    }

    prioritized: List[NationalMarketPriority] = []
    seen_keys = set()

    for priority_rank, market_key in enumerate(CORE_NATIONAL_MARKET_ORDER, start=1):
        market = MARKET_BY_KEY.get(market_key)
        readiness = readiness_by_key.get(market_key)
        if market is None or readiness is None:
            continue
        prioritized.append(
            NationalMarketPriority(
                priority_rank=priority_rank,
                market_key=market.key,
                market_name=market.name,
                coverage_scope=market.coverage_scope,
                crawl_strategy=market.crawl_strategy,
                adapter_status=readiness.adapter_status,
                adapter_family=readiness.adapter_family,
                city_target_count=readiness.city_target_count,
                priority_score=readiness.priority_score,
                official_notes=market.official_notes,
            )
        )
        seen_keys.add(market.key)

    tail_candidates = [
        market
        for market in MARKET_BY_KEY.values()
        if _is_national_market(market) and market.key not in seen_keys
    ]
    tail_candidates.sort(key=lambda market: (-readiness_by_key[market.key].priority_score, market.key))

    for market in tail_candidates:
        readiness = readiness_by_key[market.key]
        prioritized.append(
            NationalMarketPriority(
                priority_rank=len(prioritized) + 1,
                market_key=market.key,
                market_name=market.name,
                coverage_scope=market.coverage_scope,
                crawl_strategy=market.crawl_strategy,
                adapter_status=readiness.adapter_status,
                adapter_family=readiness.adapter_family,
                city_target_count=readiness.city_target_count,
                priority_score=readiness.priority_score,
                official_notes=market.official_notes,
            )
        )

    return prioritized
