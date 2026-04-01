from typing import Dict, List, Type

from .a101 import A101KapidaAdapter
from .akinon import FlormarAdapter
from .baris_gross import BarisGrossAdapter
from .bim import BimAktuelAdapter
from .carrefour import CarrefourAdapter
from .base import FetchContext, MarketAdapter, RawOffer
from .custom_html import (
    AftaMarketAdapter,
    AnkamarGiresunAdapter,
    AnkamarOrduAdapter,
    AyaydinGrossAdapter,
    BasdasAdapter,
    ErenlerAdapter,
    EskisehirMarketCategoryAdapter,
    GelsineveOrduAdapter,
    GroseriAdanaAdapter,
    GroseriMersinAdapter,
    GuvendikAdapter,
    IyasAdapter,
    IzmarAdapter,
    KDepoAdapter,
    KalafatlarAdapter,
    MarasMarketAdapter,
    SaladdoAdapter,
    ShowmarAdapter,
    SehzadeStoreAdapter,
    SozSanalMarketAdapter,
    TasoMarketAdapter,
)
from .evdesiparis import EvdesiparisSanliurfaAdapter
from .gratis import GratisAdapter
from .getir import GetirBuyukAdapter
from .ideasoft import CarmarAdapter
from .kozmela import KozmelaAdapter
from .magento import AkbalMarketAdapter
from .migros import MigrosAdapter
from .mismar import MismarAdapter
from .myikas import TShopAdapter
from .national_catalog import BizimToptanAdapter, TarimKrediKoopAdapter
from .playwright_html import YunusPlaywrightAdapter
from .rossmann import RossmannAdapter
from .shopify import BatmanSanalMarketAdapter, BingolMarketAdapter, EveShopAdapter
from .sok import SokAdapter
from .ticimax import AsyaMarketAdapter, OnurMarketKirklareliAdapter, OnurMarketTekirdagAdapter
from .woocommerce import (
    AmasyaEtUrunleriAdapter,
    AtilimSanalMarketAdapter,
    BalikesirSanalMarketAdapter,
    IsikMarketAdapter,
)
from .wordpress_rest import DelvitaAdapter
from .yeppos import KuzeyMarketAdapter
from ..market_registry import MARKET_BY_KEY


class _PlannedAdapter(MarketAdapter):
    market_key = "planned"
    market_name = "planned"
    crawl_strategy = "unknown"

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        market = MARKET_BY_KEY.get(self.market_key)
        market_name = market.name if market else self.market_name
        crawl_strategy = market.crawl_strategy if market else self.crawl_strategy
        raise NotImplementedError(
            f"{market_name} ({self.market_key}) adapteri henuz uygulanmadi. "
            f"Onerilen crawl strategy={crawl_strategy}. Context={context}"
        )


class DeferredMarketAdapter(_PlannedAdapter):
    def __init__(self, market_key: str, market_name: str, crawl_strategy: str) -> None:
        self.market_key = market_key
        self.market_name = market_name
        self.crawl_strategy = crawl_strategy


class MacroAdapter(_PlannedAdapter):
    market_key = "macroonline"


class YunusAdapter(_PlannedAdapter):
    market_key = "yunus_market_ankara"


class SehzadeAdapter(_PlannedAdapter):
    market_key = "sehzade_kayseri"


ADAPTERS: Dict[str, Type[MarketAdapter]] = {
    "bim_market": BimAktuelAdapter,
    "migros_sanal_market": MigrosAdapter,
    "carrefoursa_online_market": CarrefourAdapter,
    "a101_kapida": A101KapidaAdapter,
    "cepte_sok": SokAdapter,
    "afta_market_giresun": AftaMarketAdapter,
    "ankamar_giresun": AnkamarGiresunAdapter,
    "ankamar_ordu": AnkamarOrduAdapter,
    "asya_market_trabzon": AsyaMarketAdapter,
    "ayaydin_gross_erzincan": AyaydinGrossAdapter,
    "baris_gross_izmir": BarisGrossAdapter,
    "basdas_online_izmir": BasdasAdapter,
    "batman_sanal_market": BatmanSanalMarketAdapter,
    "bingol_market_bingol": BingolMarketAdapter,
    "eveshop_online": EveShopAdapter,
    "tshop_online": TShopAdapter,
    "carmar_diyarbakir": CarmarAdapter,
    "delvita_canakkale": DelvitaAdapter,
    "akbal_market_zonguldak": AkbalMarketAdapter,
    "amasya_et_urunleri_market_amasya": AmasyaEtUrunleriAdapter,
    "atilim_sanal_market_sakarya": AtilimSanalMarketAdapter,
    "balikesir_sanal_market": BalikesirSanalMarketAdapter,
    "bizim_toptan_online": BizimToptanAdapter,
    "flormar_online": FlormarAdapter,
    "gratis_online": GratisAdapter,
    "guvendik_erzurum": GuvendikAdapter,
    "izmar_izmir": IzmarAdapter,
    "k_depo_manisa": KDepoAdapter,
    "kalafatlar_ordu": KalafatlarAdapter,
    "kozmela_online": KozmelaAdapter,
    "kuzey_market_izmir": KuzeyMarketAdapter,
    "maras_market_kahramanmaras": MarasMarketAdapter,
    "erenler_tokat": ErenlerAdapter,
    "eskisehir_market": EskisehirMarketCategoryAdapter,
    "evdesiparis_sanliurfa": EvdesiparisSanliurfaAdapter,
    "gelsineve_ordu": GelsineveOrduAdapter,
    "getir_buyuk": GetirBuyukAdapter,
    "groseri_adana": GroseriAdanaAdapter,
    "groseri_mersin": GroseriMersinAdapter,
    "macroonline": MacroAdapter,
    "iyas_isparta": IyasAdapter,
    "isik_market_elazig": IsikMarketAdapter,
    "onur_market_kirklareli": OnurMarketKirklareliAdapter,
    "onur_market_tekirdag": OnurMarketTekirdagAdapter,
    "saladdo_antalya": SaladdoAdapter,
    "showmar_istanbul": ShowmarAdapter,
    "taso_market_kocaeli": TasoMarketAdapter,
    "rossmann_online": RossmannAdapter,
    "mismar_konya": MismarAdapter,
    "sehzade_kayseri": SehzadeStoreAdapter,
    "soz_sanal_market_afyon": SozSanalMarketAdapter,
    "tarim_kredi_koop_market": TarimKrediKoopAdapter,
    "yunus_market_ankara": YunusPlaywrightAdapter,
}


def get_adapter(market_key: str) -> MarketAdapter:
    adapter_class = ADAPTERS.get(market_key)
    if adapter_class is not None:
        return adapter_class()
    market = MARKET_BY_KEY.get(market_key)
    if market is None:
        raise KeyError(f"Bilinmeyen market adapteri: {market_key}")
    return DeferredMarketAdapter(
        market_key=market.key,
        market_name=market.name,
        crawl_strategy=market.crawl_strategy,
    )
