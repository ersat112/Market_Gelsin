from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .cities import CITIES, City
from .market_registry import MARKET_SOURCES, MarketSource


WEEKLY_FULL_REFRESH_HOURS = 24 * 7
HOT_PRODUCT_REFRESH_HOURS = 48
PRICE_HISTORY_MODE = "append_only_offer_snapshots"
IMAGE_CAPTURE_POLICY = "required"

METROPOLITAN_CITY_SLUGS: Tuple[str, ...] = (
    "adana",
    "ankara",
    "antalya",
    "aydin",
    "balikesir",
    "bursa",
    "denizli",
    "diyarbakir",
    "erzurum",
    "eskisehir",
    "gaziantep",
    "hatay",
    "istanbul",
    "izmir",
    "kahramanmaras",
    "kayseri",
    "kocaeli",
    "konya",
    "malatya",
    "manisa",
    "mardin",
    "mersin",
    "mugla",
    "ordu",
    "sakarya",
    "samsun",
    "sanliurfa",
    "tekirdag",
    "trabzon",
    "van",
)

V1_NATIONAL_CORE_MARKET_KEYS: Tuple[str, ...] = (
    "cepte_sok",
    "a101_kapida",
    "bim_market",
    "migros_sanal_market",
    "tarim_kredi_koop_market",
    "bizim_toptan_online",
    "carrefoursa_online_market",
)

ADJACENT_NATIONAL_CHANNEL_KEYS: Tuple[str, ...] = (
    "getir_buyuk",
    "watsons_online",
    "eveshop_online",
    "kozmela_online",
    "sephora_online",
    "yves_rocher_online",
    "rossmann_online",
    "flormar_online",
    "tshop_online",
    "gratis_online",
)

LOCAL_COVERAGE_SCOPES = {
    "city_specific",
    "district_cluster",
    "district_or_city_specific",
}


@dataclass(frozen=True)
class CityCollectionProgram:
    city_plate_code: int
    municipality_tier: str
    local_launch_wave: str
    coverage_goal: str
    full_refresh_hours: int
    hot_refresh_hours: int
    history_mode: str
    notes: str


@dataclass(frozen=True)
class MarketRefreshPolicy:
    market_key: str
    program_scope: str
    launch_wave: str
    full_refresh_hours: int
    hot_refresh_hours: int
    hot_refresh_enabled: bool
    image_capture_policy: str
    history_mode: str
    notes: str


def is_metropolitan_city_slug(city_slug: str) -> bool:
    return city_slug in METROPOLITAN_CITY_SLUGS


def metropolitan_city_slugs() -> Tuple[str, ...]:
    return METROPOLITAN_CITY_SLUGS


def remaining_city_slugs() -> Tuple[str, ...]:
    return tuple(city.slug for city in CITIES if city.slug not in METROPOLITAN_CITY_SLUGS)


def build_city_collection_programs() -> List[CityCollectionProgram]:
    programs: List[CityCollectionProgram] = []
    for city in CITIES:
        metropolitan = is_metropolitan_city_slug(city.slug)
        programs.append(
            CityCollectionProgram(
                city_plate_code=city.plate_code,
                municipality_tier="metropolitan_municipality" if metropolitan else "standard_province",
                local_launch_wave="v1_metro_local" if metropolitan else "v2_remaining_local",
                coverage_goal=(
                    "national_core_plus_full_local_priority"
                    if metropolitan
                    else "national_core_plus_progressive_local_expansion"
                ),
                full_refresh_hours=WEEKLY_FULL_REFRESH_HOURS,
                hot_refresh_hours=HOT_PRODUCT_REFRESH_HOURS,
                history_mode=PRICE_HISTORY_MODE,
                notes=(
                    f"{city.name} v1 metro yerel kapsama dalgasinda."
                    if metropolitan
                    else f"{city.name} v2 yerel genisleme dalgasinda; ulusal cekirdek + periyodik yerel toplama surer."
                ),
            )
        )
    return programs


def summarize_city_collection_programs(
    programs: Optional[List[CityCollectionProgram]] = None,
) -> Dict[str, int]:
    resolved = programs or build_city_collection_programs()
    summary: Dict[str, int] = {}
    for program in resolved:
        summary[program.local_launch_wave] = summary.get(program.local_launch_wave, 0) + 1
    return summary


def build_market_refresh_policies() -> List[MarketRefreshPolicy]:
    policies: List[MarketRefreshPolicy] = []
    for market in MARKET_SOURCES:
        program_scope, launch_wave, notes = _classify_market_program(market)
        policies.append(
            MarketRefreshPolicy(
                market_key=market.key,
                program_scope=program_scope,
                launch_wave=launch_wave,
                full_refresh_hours=WEEKLY_FULL_REFRESH_HOURS,
                hot_refresh_hours=HOT_PRODUCT_REFRESH_HOURS,
                hot_refresh_enabled=True,
                image_capture_policy=IMAGE_CAPTURE_POLICY,
                history_mode=PRICE_HISTORY_MODE,
                notes=notes,
            )
        )
    return policies


def summarize_market_refresh_policies(
    policies: Optional[List[MarketRefreshPolicy]] = None,
) -> Dict[str, int]:
    resolved = policies or build_market_refresh_policies()
    summary: Dict[str, int] = {}
    for policy in resolved:
        summary[policy.program_scope] = summary.get(policy.program_scope, 0) + 1
    return summary


def _classify_market_program(market: MarketSource) -> tuple[str, str, str]:
    if market.key in V1_NATIONAL_CORE_MARKET_KEYS:
        return (
            "v1_national_core",
            "v1",
            "V1 cekirdek market paketi icin haftalik tam tarama ve 48 saat hot urun yenilemesi uygulanir.",
        )
    if market.key in ADJACENT_NATIONAL_CHANNEL_KEYS:
        return (
            "adjacent_national_channel",
            "adjacent",
            "Ulusal bitisikte kanal; cekirdek market API hattindan ayri ama ayni cadence modeliyle izlenir.",
        )
    if _is_local_market(market):
        metro_local = any(is_metropolitan_city_slug(city_slug) for city_slug in (market.supported_city_slugs or ()))
        if metro_local:
            return (
                "v1_metro_local",
                "v1",
                "Buyuksehir yerel zinciri; V1 kapsamina dahil edilip tam yerel katalog hedeflenir.",
            )
        return (
            "v2_remaining_local",
            "v2",
            "Geri kalan il yerel zinciri; veri muhendisligi surer ve haftalik cadence ile genisler.",
        )
    if market.coverage_scope == "selective_metro":
        return (
            "selective_metro_backlog",
            "v2",
            "Secili metro kapsami olan kaynak; sehir kaniti netlestikce V2 genisleme dalgasina alinacak.",
        )
    return (
        "program_backlog",
        "v2",
        "Kaynak aktif registryde olsa da rollout sinifi ayrica netlestirilecek.",
    )


def _is_local_market(market: MarketSource) -> bool:
    return market.segment == "regional_chain" or market.coverage_scope in LOCAL_COVERAGE_SCOPES
