from dataclasses import dataclass
from typing import List, Optional, Tuple

from .local_discovery import VERIFIED_LOCAL_MARKET_CANDIDATES


@dataclass(frozen=True)
class MarketSource:
    key: str
    name: str
    segment: str
    coverage_scope: str
    pricing_scope: str
    crawl_strategy: str
    entrypoint_url: str
    requires_address_seed: bool
    refresh_hours: int
    official_notes: str
    target_mode: str = "all_cities_probe"
    supported_city_slugs: Optional[Tuple[str, ...]] = None


LOCAL_SOURCE_OVERRIDES = {
    "yalla_market_istanbul": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "showmar_istanbul": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "groseri_adana": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "groseri_mersin": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "afta_market_giresun": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "ankamar_giresun": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "ankamar_ordu": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "gelsineve_ordu": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "celikkayalar_konya": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "mobile_app_session",
        "requires_address_seed": True,
    },
    "hat1_hatay": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "mobile_app_session",
        "requires_address_seed": True,
    },
    "kalafatlar_ordu": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "simdi_kapida_yozgat": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "atilim_sanal_market_sakarya": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "depoo_aksaray": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "sele_karaman": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "besler_market_sivas": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "suma_kutahya": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "mobile_app_plus_site",
        "requires_address_seed": True,
    },
    "kale_market_rize": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "mobile_app_session",
        "requires_address_seed": True,
    },
    "geliver_nevsehir": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "mobile_app_session",
        "requires_address_seed": True,
    },
    "evdesiparis_sanliurfa": {
        "pricing_scope": "city_and_store",
        "crawl_strategy": "public_product_api",
        "requires_address_seed": False,
    },
    "bilmar_market_aydin": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "local_session_probe",
        "requires_address_seed": True,
    },
    "bartin_marketim_bartin": {
        "pricing_scope": "address_and_delivery_zone",
        "crawl_strategy": "mobile_app_plus_site",
        "requires_address_seed": True,
    },
}


BASE_MARKET_SOURCES = [
    MarketSource(
        key="bim_market",
        name="BIM Market",
        segment="discount_chain",
        coverage_scope="national_store_network",
        pricing_scope="channel_and_address",
        crawl_strategy="campaign_html_catalog",
        entrypoint_url="https://www.bim.com.tr/",
        requires_address_seed=False,
        refresh_hours=12,
        official_notes="Official BIM web surfaces expose priced aktuel campaign catalog pages; full BIM Market mobile assortment still requires a separate app-session discovery."
    ),
    MarketSource(
        key="migros_sanal_market",
        name="Migros Sanal Market",
        segment="national_chain",
        coverage_scope="wide_national",
        pricing_scope="store_and_address",
        crawl_strategy="sitemap_plus_store_probe",
        entrypoint_url="https://www.migros.com.tr/",
        requires_address_seed=True,
        refresh_hours=6,
        official_notes="Store-level campaigns and delivery coverage vary by location."
    ),
    MarketSource(
        key="carrefoursa_online_market",
        name="CarrefourSA Online Market",
        segment="national_chain",
        coverage_scope="wide_national",
        pricing_scope="address_and_delivery_zone",
        crawl_strategy="address_session_plus_category_api",
        entrypoint_url="https://www.carrefoursa.com/",
        requires_address_seed=True,
        refresh_hours=6,
        official_notes="City, district and neighborhood selection is required for regional pricing."
    ),
    MarketSource(
        key="tarim_kredi_koop_market",
        name="Tarim Kredi Koop Market",
        segment="national_chain",
        coverage_scope="national_store_network",
        pricing_scope="city_and_store",
        crawl_strategy="category_html_catalog",
        entrypoint_url="https://www.tkkoop.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Public category pages expose priced product cards without mandatory address selection in the observed flow."
    ),
    MarketSource(
        key="bizim_toptan_online",
        name="Bizim Toptan Online Market",
        segment="national_chain",
        coverage_scope="national_store_network",
        pricing_scope="city_and_store",
        crawl_strategy="search_html_catalog",
        entrypoint_url="https://www.bizimtoptan.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Public search and landing pages expose priced product cards; checkout and delivery options still depend on account and address."
    ),
    MarketSource(
        key="a101_kapida",
        name="A101 Kapida",
        segment="discount_chain",
        coverage_scope="national_store_network",
        pricing_scope="channel_and_address",
        crawl_strategy="search_json_catalog",
        entrypoint_url="https://www.a101.com.tr/",
        requires_address_seed=True,
        refresh_hours=6,
        official_notes="Official A101 WAW search surface exposes priced product results without storefront HTML access; deeper address-specific variations still need a later session layer."
    ),
    MarketSource(
        key="cepte_sok",
        name="Cepte Sok",
        segment="discount_chain",
        coverage_scope="national_store_network",
        pricing_scope="sales_point_and_address",
        crawl_strategy="nextjs_json_plus_product_sitemap",
        entrypoint_url="https://www.sokmarket.com.tr/",
        requires_address_seed=True,
        refresh_hours=6,
        official_notes="Stock and price vary by sales point and customer address."
    ),
    MarketSource(
        key="getir_buyuk",
        name="GetirBuyuk",
        segment="digital_grocery",
        coverage_scope="all_81_target",
        pricing_scope="address_and_service_area",
        crawl_strategy="nextjs_ssr_category_pages",
        entrypoint_url="https://getir.com/buyuk/",
        requires_address_seed=False,
        refresh_hours=4,
        official_notes="Public GetirBuyuk category pages expose a generic national catalog in Next.js state without address selection; deeper address-specific availability still requires a later session layer."
    ),
    MarketSource(
        key="watsons_online",
        name="Watsons Turkiye Online",
        segment="national_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="akamai_guarded_web_or_app",
        entrypoint_url="https://www.watsons.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Observed public web surface is protected by access controls; onboarding likely requires guarded web or app traffic analysis."
    ),
    MarketSource(
        key="eveshop_online",
        name="EveShop Online",
        segment="national_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="shopify_json_catalog",
        entrypoint_url="https://www.eveshop.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Public Shopify JSON catalog is accessible without login and appears suitable for nationwide cosmetics assortment ingestion."
    ),
    MarketSource(
        key="kozmela_online",
        name="Kozmela Online",
        segment="premium_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="custom_html_or_api_catalog",
        entrypoint_url="https://www.kozmela.com/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Observed public storefront is reachable but catalog access likely needs custom HTML or private API probing."
    ),
    MarketSource(
        key="sephora_online",
        name="Sephora Turkiye Online",
        segment="premium_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="akamai_guarded_web_or_app",
        entrypoint_url="https://www.sephora.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Observed public web surface is guarded; onboarding likely needs app or protected API discovery."
    ),
    MarketSource(
        key="yves_rocher_online",
        name="Yves Rocher Turkiye Online",
        segment="premium_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="akamai_guarded_web_or_app",
        entrypoint_url="https://www.yvesrocher.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Observed public web surface is guarded; app or protected API discovery is likely required."
    ),
    MarketSource(
        key="rossmann_online",
        name="Rossmann Online",
        segment="national_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="react_graphql_catalog",
        entrypoint_url="https://www.rossmann.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Observed storefront exposes a React front-end and hints of GraphQL-backed product flows."
    ),
    MarketSource(
        key="flormar_online",
        name="Flormar Online",
        segment="premium_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="headless_web_catalog",
        entrypoint_url="https://www.flormar.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Observed storefront is publicly reachable and appears to use a headless web catalog flow."
    ),
    MarketSource(
        key="tshop_online",
        name="T-Shop Online",
        segment="national_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="nextjs_sitemap_or_api",
        entrypoint_url="https://www.tshop.com.tr/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Observed public sitemap is reachable and the storefront appears to be a Next.js-based beauty catalog."
    ),
    MarketSource(
        key="gratis_online",
        name="Gratis Online",
        segment="national_chain",
        coverage_scope="wide_national",
        pricing_scope="channel_and_warehouse",
        crawl_strategy="product_sitemap_plus_page_parse",
        entrypoint_url="https://www.gratis.com/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Observed public product sitemap is reachable; product detail parsing can likely bootstrap a nationwide cosmetics feed."
    ),
    MarketSource(
        key="macroonline",
        name="Macroonline",
        segment="premium_chain",
        coverage_scope="selective_metro",
        pricing_scope="store_and_address",
        crawl_strategy="product_page_plus_catalog_probe",
        entrypoint_url="https://www.macrocenter.com.tr/",
        requires_address_seed=True,
        refresh_hours=8,
        official_notes="Official source indicates Macrocenter stores in 15 provinces; precise province list still needs store-level discovery.",
        target_mode="discovery_backlog",
    ),
    MarketSource(
        key="mismar_konya",
        name="Mismar Online",
        segment="regional_chain",
        coverage_scope="city_specific",
        pricing_scope="city_and_store",
        crawl_strategy="category_probe_local",
        entrypoint_url="https://www.mismarsanalmarket.com/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Current repo already contains Konya-focused Mismar scraping experiments.",
        target_mode="explicit_city_list",
        supported_city_slugs=("konya",),
    ),
    MarketSource(
        key="yunus_market_ankara",
        name="Yunus Market Online",
        segment="regional_chain",
        coverage_scope="city_specific",
        pricing_scope="city_and_store",
        crawl_strategy="category_probe_local",
        entrypoint_url="https://www.yunusonline.com/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Current repo already references Yunus Market for Ankara coverage experiments.",
        target_mode="explicit_city_list",
        supported_city_slugs=("ankara",),
    ),
    MarketSource(
        key="sehzade_kayseri",
        name="Sehzade Online",
        segment="regional_chain",
        coverage_scope="city_specific",
        pricing_scope="city_and_store",
        crawl_strategy="category_probe_local",
        entrypoint_url="https://sehzadeonline.com/",
        requires_address_seed=False,
        refresh_hours=8,
        official_notes="Current repo already references Sehzade for Kayseri coverage experiments.",
        target_mode="explicit_city_list",
        supported_city_slugs=("kayseri",),
    ),
]


def _candidate_key(candidate_slug: str) -> str:
    return candidate_slug.replace("-", "_")


def _candidate_pricing_scope(candidate_key: str, market_scope: str) -> str:
    override = LOCAL_SOURCE_OVERRIDES.get(candidate_key, {})
    if "pricing_scope" in override:
        return override["pricing_scope"]
    if "district" in market_scope:
        return "district_and_store"
    return "city_and_store"


def _candidate_crawl_strategy(candidate_key: str) -> str:
    return LOCAL_SOURCE_OVERRIDES.get(candidate_key, {}).get("crawl_strategy", "local_storefront_probe")


def _candidate_requires_address_seed(candidate_key: str, market_scope: str) -> bool:
    override = LOCAL_SOURCE_OVERRIDES.get(candidate_key, {})
    if "requires_address_seed" in override:
        return bool(override["requires_address_seed"])
    return "district" in market_scope


def _promoted_local_market_sources() -> List[MarketSource]:
    existing_keys = {market.key for market in BASE_MARKET_SOURCES}
    promoted: List[MarketSource] = []
    for candidate in VERIFIED_LOCAL_MARKET_CANDIDATES:
        candidate_key = _candidate_key(candidate.market_slug)
        if candidate_key in existing_keys:
            continue
        promoted.append(
            MarketSource(
                key=candidate_key,
                name=candidate.market_name,
                segment="regional_chain",
                coverage_scope=candidate.market_scope,
                pricing_scope=_candidate_pricing_scope(candidate_key, candidate.market_scope),
                crawl_strategy=_candidate_crawl_strategy(candidate_key),
                entrypoint_url=candidate.entrypoint_url,
                requires_address_seed=_candidate_requires_address_seed(candidate_key, candidate.market_scope),
                refresh_hours=8,
                official_notes=candidate.notes,
                target_mode="explicit_city_list",
                supported_city_slugs=(candidate.city_slug,),
            )
        )
    return promoted


MARKET_SOURCES = BASE_MARKET_SOURCES + _promoted_local_market_sources()


MARKET_BY_KEY = {market.key: market for market in MARKET_SOURCES}
