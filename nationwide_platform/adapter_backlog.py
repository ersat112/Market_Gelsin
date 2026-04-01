from dataclasses import dataclass
from typing import Dict, List

from .market_registry import MARKET_SOURCES, MarketSource
from .planner import build_default_targets, summarize_targets


@dataclass(frozen=True)
class AdapterReadiness:
    market_key: str
    adapter_status: str
    adapter_family: str
    complexity_level: str
    city_target_count: int
    priority_score: int
    notes: str


@dataclass(frozen=True)
class AdapterBacklogItem:
    market_key: str
    adapter_family: str
    city_target_count: int
    complexity_level: str
    recommended_next_step: str
    priority_score: int
    notes: str


IMPLEMENTED_MARKETS = {
    "a101_kapida",
    "bim_market",
    "migros_sanal_market",
    "carrefoursa_online_market",
    "cepte_sok",
    "eveshop_online",
    "tshop_online",
    "kozmela_online",
    "mismar_konya",
    "afta_market_giresun",
    "ankamar_giresun",
    "ankamar_ordu",
    "asya_market_trabzon",
    "ayaydin_gross_erzincan",
    "baris_gross_izmir",
    "basdas_online_izmir",
    "batman_sanal_market",
    "carmar_diyarbakir",
    "delvita_canakkale",
    "eskisehir_market",
    "akbal_market_zonguldak",
    "amasya_et_urunleri_market_amasya",
    "atilim_sanal_market_sakarya",
    "balikesir_sanal_market",
    "bizim_toptan_online",
    "flormar_online",
    "gratis_online",
    "rossmann_online",
    "erenler_tokat",
    "evdesiparis_sanliurfa",
    "gelsineve_ordu",
    "getir_buyuk",
    "groseri_adana",
    "groseri_mersin",
    "guvendik_erzurum",
    "iyas_isparta",
    "isik_market_elazig",
    "izmar_izmir",
    "k_depo_manisa",
    "kalafatlar_ordu",
    "kuzey_market_izmir",
    "maras_market_kahramanmaras",
    "onur_market_kirklareli",
    "onur_market_tekirdag",
    "saladdo_antalya",
    "showmar_istanbul",
    "taso_market_kocaeli",
    "sehzade_kayseri",
    "soz_sanal_market_afyon",
    "tarim_kredi_koop_market",
    "yunus_market_ankara",
}


ADAPTER_FAMILY_OVERRIDES: Dict[str, str] = {
    "bim_market": "campaign_html_catalog",
    "migros_sanal_market": "rest_json_catalog",
    "cepte_sok": "nextjs_json_storefront",
    "carrefoursa_online_market": "category_search_catalog",
    "a101_kapida": "search_json_catalog",
    "getir_buyuk": "nextjs_ssr_category_pages",
    "watsons_online": "akamai_guarded_web_or_app",
    "eveshop_online": "shopify_json_catalog",
    "kozmela_online": "custom_html_or_api_catalog",
    "sephora_online": "akamai_guarded_web_or_app",
    "yves_rocher_online": "akamai_guarded_web_or_app",
    "rossmann_online": "react_graphql_catalog",
    "flormar_online": "headless_web_catalog",
    "tshop_online": "nextjs_sitemap_or_api",
    "gratis_online": "product_sitemap_plus_page_parse",
    "macroonline": "address_session_web",
    "groseri_adana": "catalog_or_collection_pages",
    "groseri_mersin": "catalog_or_collection_pages",
    "yalla_market_istanbul": "address_session_web",
    "showmar_istanbul": "address_session_web",
    "yunus_market_ankara": "playwright_html_catalog",
    "afta_market_giresun": "address_session_web",
    "ankamar_giresun": "gelsineve_catalog",
    "ankamar_ordu": "gelsineve_catalog",
    "gelsineve_ordu": "address_session_web",
    "kalafatlar_ordu": "kommerz_ajax_catalog",
    "simdi_kapida_yozgat": "address_session_web",
    "depoo_aksaray": "mobile_app_session",
    "sele_karaman": "mobile_app_session",
    "besler_market_sivas": "mobile_app_session",
    "kale_market_rize": "mobile_app_session",
    "geliver_nevsehir": "mobile_app_session",
    "suma_kutahya": "mobile_app_plus_site",
    "kahta_online_market_adiyaman": "mobile_app_plus_site",
}


def _adapter_family(market: MarketSource) -> str:
    override = ADAPTER_FAMILY_OVERRIDES.get(market.key)
    if override:
        return override
    if "sitemap" in market.crawl_strategy:
        return "sitemap_product_pages"
    if "nextjs" in market.crawl_strategy:
        return "nextjs_json_storefront"
    if market.requires_address_seed:
        return "address_session_web"
    return "catalog_or_collection_pages"


def _complexity_level(market: MarketSource, adapter_family: str) -> str:
    if adapter_family in {"mobile_app_session", "address_session_web_or_app", "akamai_guarded_web_or_app"}:
        return "high"
    if adapter_family in {
        "address_session_web",
        "mobile_app_plus_site",
        "react_graphql_catalog",
        "headless_web_catalog",
        "nextjs_sitemap_or_api",
        "custom_html_or_api_catalog",
        "product_sitemap_plus_page_parse",
    }:
        return "medium"
    if market.requires_address_seed:
        return "medium"
    return "low"


def _priority_score(market: MarketSource, city_target_count: int, complexity_level: str, adapter_status: str) -> int:
    status_bonus = 0 if adapter_status == "live" else 20
    complexity_bonus = {"low": 20, "medium": 12, "high": 6}[complexity_level]
    national_bonus = {
        "national_chain": 30,
        "discount_chain": 28,
        "digital_grocery": 28,
        "premium_chain": 18,
        "regional_chain": 12,
    }.get(market.segment, 10)
    return min(100, city_target_count + status_bonus + complexity_bonus + national_bonus)


def _notes_for_market(market: MarketSource, adapter_family: str, adapter_status: str) -> str:
    if adapter_status == "live":
        return f"{market.name} zaten veri akitiyor. Bakim ve kalite iyilestirmesi odakli ilerlenmeli."
    if adapter_family == "address_session_web":
        return f"{market.name} adres veya teslimat bolgesi secimi gerektiriyor; session yakalama ve kategori probe gerekli."
    if adapter_family == "mobile_app_session":
        return f"{market.name} icin resmi uygulama veya mobil API tabakasi incelenmeli."
    if adapter_family == "mobile_app_plus_site":
        return f"{market.name} icin hem resmi domain hem de uygulama davranisi birlikte cozulmeli."
    if adapter_family == "akamai_guarded_web_or_app":
        return f"{market.name} icin korumali web akisina ek olarak mobil uygulama veya API katmani arastirilmali."
    return f"{market.name} icin katalog veya koleksiyon sayfasi tabanli bir adapter yazilabilir."


def _recommended_next_step(adapter_family: str) -> str:
    mapping = {
        "address_session_web": "Address seed + session cookie yakala, kategori veya arama endpointlerini tespit et.",
        "address_session_web_or_app": "Web ve uygulama akislarini karsilastir, daha stabil endpoint katmanini sec.",
        "mobile_app_session": "Uygulama trafik akisini incele, kimliksiz urun listeleme endpointi varsa once onu bagla.",
        "mobile_app_plus_site": "Domain ve uygulama listingi arasinda ortak urun kaynagini bul, sonra hafif adapter yaz.",
        "campaign_html_catalog": "Resmi kampanya veya aktuel liste sayfalarindan urun kartlarini ve fiyatlari parse et.",
        "sitemap_product_pages": "Sitemap ve urun sayfasi parseri ile hizli MVP adapteri tamamla.",
        "rest_json_catalog": "Kategori JSON endpointlerini sayfalama ile tara, fiyat ve stok payloadini dogrudan bagla.",
        "search_json_catalog": "Resmi arama JSON yuzeyini tam katalog sorgusu ile tara, sonra urun kayitlarini normalize et.",
        "nextjs_json_storefront": "Storefront JSON payloadini parse ederek urun listesi ve fiyat katmanini bagla.",
        "catalog_or_collection_pages": "Kategori sayfalari ve urun kartlari uzerinden hafif HTML adapteri yaz.",
        "shopify_json_catalog": "Shopify products.json veya collection feedlerini sayfalama ile tara ve varyant fiyatlarini normalize et.",
        "product_sitemap_plus_page_parse": "Urun sitemap'ini tara, detay sayfalarindan fiyat ve stok verisini parse et.",
        "react_graphql_catalog": "React storefront icindeki GraphQL veya API cagrilarini belirleyip urun listing akisini bagla.",
        "headless_web_catalog": "Headless storefront tarafinda istemci veri kaynaklarini yakala ve katalog endpointini normalize et.",
        "nextjs_sitemap_or_api": "Next.js sitemap, build manifest ve istemci fetch cagrilarini kullanarak urun katalogunu cikar.",
        "custom_html_or_api_catalog": "Sayfa HTML'i ve gizli API cagrilarini birlikte tarayip en stabil katalog yolunu sec.",
        "akamai_guarded_web_or_app": "Korumali web yuzeyi yerine mobil uygulama, public asset veya arka API adaylarini arastir.",
    }
    return mapping.get(adapter_family, "Storefront yapisini cikar ve en dusuk maliyetli tarama yolunu sec.")


def build_adapter_readiness() -> List[AdapterReadiness]:
    target_summary = summarize_targets(build_default_targets())
    readiness_rows: List[AdapterReadiness] = []
    for market in MARKET_SOURCES:
        adapter_status = "live" if market.key in IMPLEMENTED_MARKETS else "planned"
        adapter_family = _adapter_family(market)
        complexity_level = _complexity_level(market, adapter_family)
        city_target_count = target_summary.get(market.key, 0)
        priority_score = _priority_score(market, city_target_count, complexity_level, adapter_status)
        readiness_rows.append(
            AdapterReadiness(
                market_key=market.key,
                adapter_status=adapter_status,
                adapter_family=adapter_family,
                complexity_level=complexity_level,
                city_target_count=city_target_count,
                priority_score=priority_score,
                notes=_notes_for_market(market, adapter_family, adapter_status),
            )
        )
    return readiness_rows


def build_adapter_backlog() -> List[AdapterBacklogItem]:
    backlog: List[AdapterBacklogItem] = []
    for readiness in build_adapter_readiness():
        if readiness.adapter_status == "live":
            continue
        backlog.append(
            AdapterBacklogItem(
                market_key=readiness.market_key,
                adapter_family=readiness.adapter_family,
                city_target_count=readiness.city_target_count,
                complexity_level=readiness.complexity_level,
                recommended_next_step=_recommended_next_step(readiness.adapter_family),
                priority_score=readiness.priority_score,
                notes=readiness.notes,
            )
        )
    backlog.sort(key=lambda item: (-item.priority_score, -item.city_target_count, item.market_key))
    return backlog
