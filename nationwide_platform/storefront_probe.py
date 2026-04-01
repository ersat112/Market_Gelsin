import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .adapter_backlog import IMPLEMENTED_MARKETS
from .market_registry import MARKET_SOURCES, MarketSource


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
BLOCKED_URL_TOKENS = (
    "mailto:",
    "tel:",
    "javascript:",
    "#",
    "/hakkimizda",
    "/iletisim",
    "/subeler",
    "/kariyer",
    "/blog",
    "/haber",
    "/gizlilik",
    "/kvkk",
    "/uyelik",
    "/giris",
)
BLOCKED_HOST_TOKENS = (
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "youtube.com",
    "youtu.be",
    "google.com",
    "goo.gl",
    "linkedin.com",
)
CATEGORY_HINTS = (
    "/kategoriler/",
    "/kategori/",
    "/product-category/",
    "/c-",
    "/shop",
    "/urunler",
    "/collections/",
    "/category/",
)
EXTERNAL_STOREFRONT_HINTS = (
    "sanal",
    "online",
    "alisveris",
    "shop",
    "market",
    "e-ticaret",
)
APP_ONLY_HINTS = (
    "apps.apple.com",
    "app store",
    "play.google.com",
    "google play",
    "onelink.to",
    "uygulamayi indir",
    "uygulamamizi indir",
    "mobil uygulama",
)


@dataclass(frozen=True)
class MarketStorefrontProbe:
    market_key: str
    probe_scope: str
    storefront_family: str
    product_flow_status: str
    recommended_adapter_family: str
    homepage_url: str
    final_url: Optional[str]
    http_status: Optional[int]
    sample_url: Optional[str]
    sample_product_count: int
    signals_json: str
    notes: str
    last_probed_at: str


@dataclass(frozen=True)
class _FetchResult:
    url: str
    final_url: Optional[str]
    status_code: Optional[int]
    text: str
    transport: str
    error: Optional[str]


class StorefrontProbeRunner:
    def __init__(self, request_timeout: int = 8, max_retries: int = 0):
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "tr-TR,tr;q=0.9"})

    def probe_market(self, market: MarketSource, probe_scope: str = "remaining_local_non_live") -> MarketStorefrontProbe:
        started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        homepage = self._fetch_text(market.entrypoint_url)
        home_signals = self._build_signals(homepage.text)
        storefront_family = self._detect_storefront_family(homepage, home_signals)
        recommended_family = self._recommended_adapter_family(storefront_family)
        notes: List[str] = []

        if homepage.error:
            notes.append(f"homepage_fetch_error={homepage.error}")

        if self._looks_blocked(homepage.text):
            return self._result(
                market=market,
                probe_scope=probe_scope,
                storefront_family=storefront_family,
                product_flow_status="blocked_challenge",
                recommended_adapter_family=recommended_family,
                homepage=homepage,
                sample_url=None,
                sample_product_count=0,
                signals=self._serialize_signals(home_signals, storefront_family, None, None),
                notes="Fingerprint veya challenge davranisi tespit edildi.",
                last_probed_at=started_at,
            )

        if homepage.status_code is None and homepage.error:
            return self._result(
                market=market,
                probe_scope=probe_scope,
                storefront_family=storefront_family,
                product_flow_status="network_error",
                recommended_adapter_family=recommended_family,
                homepage=homepage,
                sample_url=None,
                sample_product_count=0,
                signals=self._serialize_signals(home_signals, storefront_family, None, None),
                notes="Homepage erisimi ag hatasi verdi.",
                last_probed_at=started_at,
            )

        if storefront_family == "mobile_app_only":
            return self._result(
                market=market,
                probe_scope=probe_scope,
                storefront_family=storefront_family,
                product_flow_status="app_only",
                recommended_adapter_family="mobile_app_session",
                homepage=homepage,
                sample_url=homepage.final_url or market.entrypoint_url,
                sample_product_count=0,
                signals=self._serialize_signals(home_signals, storefront_family, None, None),
                notes="Public web yuzeyi katalog yerine App Store / Google Play / OneLink mobil koprusu gosteriyor.",
                last_probed_at=started_at,
            )

        category_urls = self._candidate_urls(homepage.text, homepage.final_url or market.entrypoint_url)
        endpoint_signals = self._probe_store_api(homepage.final_url or market.entrypoint_url, storefront_family)
        if endpoint_signals["sample_product_count"] > 0:
            return self._result(
                market=market,
                probe_scope=probe_scope,
                storefront_family=storefront_family,
                product_flow_status="open_product_flow",
                recommended_adapter_family=endpoint_signals["recommended_adapter_family"],
                homepage=homepage,
                sample_url=endpoint_signals["sample_url"],
                sample_product_count=endpoint_signals["sample_product_count"],
                signals=self._serialize_signals(home_signals, storefront_family, endpoint_signals, None),
                notes=endpoint_signals["notes"],
                last_probed_at=started_at,
            )

        best_candidate = None
        for category_url in category_urls[:5]:
            candidate_fetch = self._fetch_text(category_url)
            candidate_signals = self._build_signals(candidate_fetch.text)
            candidate_family = self._detect_storefront_family(candidate_fetch, candidate_signals)
            candidate_endpoint_signals = self._probe_store_api(
                candidate_fetch.final_url or category_url,
                candidate_family,
            )
            if candidate_endpoint_signals["sample_product_count"] > 0:
                return self._result(
                    market=market,
                    probe_scope=probe_scope,
                    storefront_family=candidate_endpoint_signals["storefront_family"],
                    product_flow_status="open_product_flow",
                    recommended_adapter_family=candidate_endpoint_signals["recommended_adapter_family"],
                    homepage=homepage,
                    sample_url=candidate_endpoint_signals["sample_url"],
                    sample_product_count=candidate_endpoint_signals["sample_product_count"],
                    signals=self._serialize_signals(home_signals, storefront_family, candidate_endpoint_signals, None),
                    notes=candidate_endpoint_signals["notes"],
                    last_probed_at=started_at,
                )
            open_flow = self._classify_candidate_page(candidate_fetch, candidate_signals)
            if (
                best_candidate is None
                or open_flow["sample_product_count"] > best_candidate["result"]["sample_product_count"]
            ):
                best_candidate = {
                    "url": category_url,
                    "fetch": candidate_fetch,
                    "signals": candidate_signals,
                    "result": open_flow,
                }
            if open_flow["product_flow_status"] == "open_product_flow":
                return self._result(
                    market=market,
                    probe_scope=probe_scope,
                    storefront_family=open_flow["storefront_family"] or storefront_family,
                    product_flow_status="open_product_flow",
                    recommended_adapter_family=open_flow["recommended_adapter_family"],
                    homepage=homepage,
                    sample_url=category_url,
                    sample_product_count=open_flow["sample_product_count"],
                    signals=self._serialize_signals(home_signals, storefront_family, endpoint_signals, best_candidate),
                    notes=open_flow["notes"],
                    last_probed_at=started_at,
                )

        if best_candidate and best_candidate["result"]["product_flow_status"] != "corp_site_only":
            open_flow = best_candidate["result"]
            notes.append(open_flow["notes"])
            return self._result(
                market=market,
                probe_scope=probe_scope,
                storefront_family=open_flow["storefront_family"] or storefront_family,
                product_flow_status=open_flow["product_flow_status"],
                recommended_adapter_family=open_flow["recommended_adapter_family"],
                homepage=homepage,
                sample_url=best_candidate["url"],
                sample_product_count=open_flow["sample_product_count"],
                signals=self._serialize_signals(home_signals, storefront_family, endpoint_signals, best_candidate),
                notes="; ".join(note for note in notes if note),
                last_probed_at=started_at,
            )

        return self._result(
            market=market,
            probe_scope=probe_scope,
            storefront_family=storefront_family,
            product_flow_status="corp_site_only",
            recommended_adapter_family=recommended_family,
            homepage=homepage,
            sample_url=None,
            sample_product_count=0,
            signals=self._serialize_signals(home_signals, storefront_family, endpoint_signals, best_candidate),
            notes="Acilis sayfasi ve kategori linkleri icinde acik urun akisi bulunamadi.",
            last_probed_at=started_at,
        )

    def _fetch_text(self, url: str) -> _FetchResult:
        last_error: Optional[str] = None
        for _ in range(self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.request_timeout, allow_redirects=True)
                response.encoding = "utf-8"
                return _FetchResult(
                    url=url,
                    final_url=response.url,
                    status_code=response.status_code,
                    text=response.text or "",
                    transport="requests",
                    error=None,
                )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        completed = subprocess.run(
            [
                "curl",
                "-L",
                "-k",
                "--silent",
                "--show-error",
                "--max-time",
                str(self.request_timeout),
                "--url",
                url,
                "-A",
                USER_AGENT,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout:
            return _FetchResult(
                url=url,
                final_url=url,
                status_code=200,
                text=completed.stdout,
                transport="curl",
                error=None,
            )
        curl_error = completed.stderr.strip() or None
        return _FetchResult(
            url=url,
            final_url=None,
            status_code=None,
            text="",
            transport="curl",
            error=curl_error or last_error or "unknown_fetch_error",
        )

    @staticmethod
    def _looks_blocked(text: str) -> bool:
        lowered = text.lower()
        return "fingerprint" in lowered or "cf-chl" in lowered or "redirect_link" in lowered

    @staticmethod
    def _build_signals(text: str) -> Dict[str, object]:
        lowered = text.lower()
        return {
            "contains_woocommerce": "woocommerce" in lowered or "wp-json" in lowered,
            "contains_wp_json": "wp-json" in lowered,
            "contains_shopify": "shopify" in lowered,
            "contains_nextjs": "__NEXT_DATA__" in text,
            "contains_tsoft_legacy": "PRODUCT_DATA.push" in text or "Add2Cart(" in text or "vitrin-urun-adi" in text,
            "contains_gelsineve": "/kategoriler/" in lowered and "/urun/" in lowered,
            "contains_showcase": "showcase-title" in lowered,
            "contains_tsoft_modern": "data-toggle='product'" in text or 'data-toggle="product"' in text,
            "contains_opencart": "route=product/search" in lowered or "product-thumb" in lowered,
            "contains_wix": "data-hook=\"product-item-root\"" in text or "data-hook='product-item-root'" in text,
            "contains_prestashop": "data-id-product" in lowered or "#js-product-list" in lowered,
            "contains_ideasoft": "arama_v3_urunler.asp" in lowered or "urun-kutusu" in lowered,
            "contains_app_store_link": "apps.apple.com" in lowered or "app store" in lowered,
            "contains_google_play_link": "play.google.com" in lowered or "google play" in lowered,
            "contains_onelink": "onelink.to" in lowered,
            "contains_app_download_cta": any(hint in lowered for hint in APP_ONLY_HINTS),
            "product_card_count": sum(
                (
                    text.count('class="product"'),
                    text.count("productItem"),
                    text.count("showcase-title"),
                    text.count("data-id-product"),
                    text.count("urun-kutusu"),
                    text.count("product-thumb"),
                )
            ),
        }

    @staticmethod
    def _detect_storefront_family(fetch: _FetchResult, signals: Dict[str, object]) -> str:
        if (
            signals["contains_app_download_cta"]
            and not signals["contains_woocommerce"]
            and not signals["contains_shopify"]
            and not signals["contains_nextjs"]
            and not signals["contains_ideasoft"]
            and signals["product_card_count"] == 0
        ):
            return "mobile_app_only"
        if signals["contains_gelsineve"]:
            return "gelsineve_catalog"
        if signals["contains_tsoft_legacy"]:
            return "tsoft_legacy_grid"
        if signals["contains_showcase"]:
            return "showcase_category"
        if signals["contains_tsoft_modern"]:
            return "tsoft_category"
        if signals["contains_opencart"]:
            return "opencart_search"
        if signals["contains_wix"]:
            return "wix_stores"
        if signals["contains_prestashop"]:
            return "prestashop_elementor_catalog"
        if signals["contains_ideasoft"]:
            return "ideasoft_html"
        if signals["contains_nextjs"]:
            return "nextjs_card_catalog"
        if signals["contains_woocommerce"]:
            return "woocommerce_candidate"
        if fetch.error:
            return "network_unreachable"
        return "generic_html"

    @staticmethod
    def _recommended_adapter_family(storefront_family: str) -> str:
        mapping = {
            "gelsineve_catalog": "gelsineve_catalog",
            "tsoft_legacy_grid": "tsoft_legacy_grid",
            "showcase_category": "showcase_category",
            "tsoft_category": "tsoft_category",
            "opencart_search": "opencart_search",
            "wix_stores": "wix_stores",
            "prestashop_elementor_catalog": "prestashop_elementor_catalog",
            "ideasoft_html": "ideasoft_or_custom_html",
            "nextjs_card_catalog": "nextjs_card_catalog",
            "woocommerce_candidate": "woocommerce_html",
            "wordpress_rest_product": "wordpress_rest_product",
            "mobile_app_only": "mobile_app_session",
            "generic_html": "manual_probe_required",
            "network_unreachable": "manual_probe_required",
        }
        return mapping.get(storefront_family, "manual_probe_required")

    def _probe_store_api(self, homepage_url: str, storefront_family: str) -> Dict[str, object]:
        endpoint_urls: Sequence[Tuple[str, str]] = ()
        if storefront_family == "woocommerce_candidate":
            endpoint_urls = (
                ("woocommerce_store_api", urljoin(homepage_url, "/wp-json/wc/store/products?per_page=2")),
                ("woocommerce_store_api", urljoin(homepage_url, "/wp-json/wc/store/v1/products?per_page=2")),
                ("wordpress_rest_product", urljoin(homepage_url, "/wp-json/wp/v2/product?per_page=2")),
            )

        for family, endpoint_url in endpoint_urls:
            fetch = self._fetch_text(endpoint_url)
            if fetch.status_code != 200 or not fetch.text:
                continue
            try:
                payload = json.loads(fetch.text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, list) and payload:
                if self._looks_like_demo_payload(payload):
                    return {
                        "storefront_family": family,
                        "recommended_adapter_family": self._recommended_adapter_family(storefront_family),
                        "sample_url": endpoint_url,
                        "sample_product_count": 0,
                        "notes": "Store API acik ancak donen urunler demo/lorem ipsum katalog gibi gorunuyor.",
                    }
                if family == "wordpress_rest_product":
                    return {
                        "storefront_family": family,
                        "recommended_adapter_family": "wordpress_rest_product",
                        "sample_url": endpoint_url,
                        "sample_product_count": len(payload),
                        "notes": "WordPress REST product endpoint'i yayinlanmis urunler donduruyor.",
                    }
                return {
                    "storefront_family": family,
                    "recommended_adapter_family": "woocommerce_html",
                    "sample_url": endpoint_url,
                    "sample_product_count": len(payload),
                    "notes": "WooCommerce Store API acik ve urun listesi donduruyor.",
                }
        return {
            "storefront_family": storefront_family,
            "recommended_adapter_family": self._recommended_adapter_family(storefront_family),
            "sample_url": None,
            "sample_product_count": 0,
            "notes": "Acilis sayfasi API probe asamasinda acik urun endpointi vermedi.",
        }

    @staticmethod
    def _looks_like_demo_payload(payload: List[dict]) -> bool:
        demo_markers = ("lorem ipsum", "nibh euismod", "dummy", "demo")
        for product in payload[:3]:
            text_parts = [
                str(product.get("name") or ""),
                str(product.get("short_description") or ""),
                str(product.get("description") or ""),
            ]
            combined = " ".join(text_parts).lower()
            if any(marker in combined for marker in demo_markers):
                return True
        return False

    def _candidate_urls(self, html_text: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html_text, "html.parser")
        parsed_base = urlparse(base_url)
        scored_urls: Dict[str, int] = {}
        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            anchor_text = " ".join(anchor.get_text(" ", strip=True).split()).lower()
            if not href:
                continue
            normalized = urljoin(base_url, href)
            parsed = urlparse(normalized)
            if parsed.scheme not in {"http", "https"}:
                continue
            lowered = normalized.lower()
            if any(host_token in parsed.netloc.lower() for host_token in BLOCKED_HOST_TOKENS):
                continue
            is_external = bool(parsed.netloc and parsed_base.netloc and parsed.netloc != parsed_base.netloc)
            if is_external:
                related_score = self._related_host_score(parsed_base.netloc, parsed.netloc)
                has_store_hint = any(token in lowered or token in anchor_text for token in EXTERNAL_STOREFRONT_HINTS)
                if related_score <= 0 or not has_store_hint:
                    continue
            else:
                related_score = 0
            if any(token in lowered for token in BLOCKED_URL_TOKENS):
                continue
            score = 0
            if any(token in lowered for token in CATEGORY_HINTS):
                score += 8
            if any(token in lowered for token in EXTERNAL_STOREFRONT_HINTS):
                score += 5
            if any(token in anchor_text for token in EXTERNAL_STOREFRONT_HINTS):
                score += 4
            if "/kategoriler/" in lowered:
                score += 12
            if "/product-category/" in lowered:
                score += 11
            if re.search(r"/c-\d+", lowered):
                score += 10
            if "/kategori/" in lowered:
                score += 9
            if "/urun/" in lowered:
                score -= 1
            if parsed.path.count("/") >= 2:
                score += 1
            score += related_score
            if score <= 0:
                continue
            previous = scored_urls.get(normalized, -1)
            if score > previous:
                scored_urls[normalized] = score
        return [url for url, _ in sorted(scored_urls.items(), key=lambda item: (-item[1], item[0]))]

    @staticmethod
    def _related_host_score(base_netloc: str, candidate_netloc: str) -> int:
        def normalize_host(host: str) -> str:
            return re.sub(r"[^a-z0-9]", "", host.lower().removeprefix("www."))

        base_host = normalize_host(base_netloc)
        candidate_host = normalize_host(candidate_netloc)
        if not base_host or not candidate_host:
            return 0
        if base_host == candidate_host:
            return 8
        if base_host[:5] and base_host[:5] in candidate_host:
            return 7
        if candidate_host[:5] and candidate_host[:5] in base_host:
            return 7

        common_prefix = 0
        for base_char, candidate_char in zip(base_host, candidate_host):
            if base_char != candidate_char:
                break
            common_prefix += 1
        if common_prefix >= 4:
            return 6
        return 0

    def _classify_candidate_page(self, fetch: _FetchResult, signals: Dict[str, object]) -> Dict[str, object]:
        text = fetch.text
        lowered = text.lower()
        soup = BeautifulSoup(text, "html.parser")

        detectors = [
            ("tsoft_legacy_grid", "tsoft_legacy_grid", len(soup.select("div.productItem"))),
            ("tsoft_category", "tsoft_category", len(soup.select("[data-toggle='product']"))),
            ("showcase_category", "showcase_category", len(soup.select(".showcase"))),
            ("wix_stores", "wix_stores", len(soup.select("[data-hook='product-item-root']"))),
            ("prestashop_elementor_catalog", "prestashop_elementor_catalog", len(soup.select("#js-product-list article[data-id-product]"))),
            ("opencart_search", "opencart_search", len(soup.select(".product-layout .product-thumb"))),
            ("ideasoft_or_custom_html", "ideasoft_html", len(soup.select(".urun-kutusu"))),
            (
                "gelsineve_catalog",
                "gelsineve_catalog",
                len(
                    [
                        card
                        for card in soup.select(".product")
                        if card.select_one(".new-price") is not None and card.select_one("a[href*='/urun/']") is not None
                    ]
                ),
            ),
            ("woocommerce_html", "woocommerce_candidate", len(soup.select("li.product"))),
        ]

        for adapter_family, storefront_family, count in detectors:
            if count > 0:
                return {
                    "product_flow_status": "open_product_flow",
                    "recommended_adapter_family": adapter_family,
                    "storefront_family": storefront_family,
                    "sample_product_count": count,
                    "notes": f"Kategori sayfasi uzerinde {count} urun karti bulundu.",
                }

        if "sepete ekle" in lowered or "/urun/" in lowered or "/product/" in lowered:
            return {
                "product_flow_status": "catalog_visible_no_cards",
                "recommended_adapter_family": self._recommended_adapter_family(self._detect_storefront_family(fetch, signals)),
                "storefront_family": self._detect_storefront_family(fetch, signals),
                "sample_product_count": 0,
                "notes": "Kategori veya urun linkleri gorunuyor ancak dogrudan parsera uygun urun karti bulunamadi.",
            }

        return {
            "product_flow_status": "corp_site_only",
            "recommended_adapter_family": self._recommended_adapter_family(self._detect_storefront_family(fetch, signals)),
            "storefront_family": self._detect_storefront_family(fetch, signals),
            "sample_product_count": 0,
            "notes": "Kategori/prod karti yerine tanitim veya kurumsal icerik dondu.",
        }

    @staticmethod
    def _serialize_signals(
        homepage_signals: Dict[str, object],
        homepage_family: str,
        endpoint_signals: Optional[Dict[str, object]],
        best_candidate: Optional[Dict[str, object]],
    ) -> str:
        payload = {
            "homepage_family": homepage_family,
            "homepage_signals": homepage_signals,
            "endpoint_probe": endpoint_signals,
        }
        if best_candidate is not None:
            payload["best_candidate"] = {
                "url": best_candidate["url"],
                "signals": best_candidate["signals"],
                "result": best_candidate["result"],
                "status_code": best_candidate["fetch"].status_code,
            }
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)

    @staticmethod
    def _result(
        market: MarketSource,
        probe_scope: str,
        storefront_family: str,
        product_flow_status: str,
        recommended_adapter_family: str,
        homepage: _FetchResult,
        sample_url: Optional[str],
        sample_product_count: int,
        signals: str,
        notes: str,
        last_probed_at: str,
    ) -> MarketStorefrontProbe:
        return MarketStorefrontProbe(
            market_key=market.key,
            probe_scope=probe_scope,
            storefront_family=storefront_family,
            product_flow_status=product_flow_status,
            recommended_adapter_family=recommended_adapter_family,
            homepage_url=market.entrypoint_url,
            final_url=homepage.final_url,
            http_status=homepage.status_code,
            sample_url=sample_url,
            sample_product_count=sample_product_count,
            signals_json=signals,
            notes=notes,
            last_probed_at=last_probed_at,
        )


def build_probe_targets(include_live: bool = False) -> List[MarketSource]:
    targets = [
        market
        for market in MARKET_SOURCES
        if market.supported_city_slugs
        and market.segment == "regional_chain"
        and (include_live or market.key not in IMPLEMENTED_MARKETS)
    ]
    targets.sort(key=lambda market: (market.supported_city_slugs or tuple(), market.name, market.key))
    return targets


def probe_remaining_local_markets(include_live: bool = False) -> List[MarketStorefrontProbe]:
    runner = StorefrontProbeRunner()
    return [runner.probe_market(market) for market in build_probe_targets(include_live=include_live)]
