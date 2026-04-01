import json
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import FetchContext, MarketAdapter, RawOffer

try:
    import cloudscraper
except ImportError:  # pragma: no cover
    cloudscraper = None


class GetirBuyukAdapter(MarketAdapter):
    market_key = "getir_buyuk"
    base_url = "https://getir.com"

    def __init__(
        self,
        max_products: int = 12000,
        max_categories: int = 24,
        request_timeout: int = 25,
        max_retries: int = 2,
    ) -> None:
        self.max_products = max_products
        self.max_categories = max_categories
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.session = self._build_session()
        self.scraper = self._build_scraper()

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()

        for category_slug, category_name in self._discover_categories():
            state = self._fetch_category_state(category_slug)
            if not state:
                continue

            getir_listing = state.get("getirListing") or {}
            active_categories = getir_listing.get("activeCategories") or {}
            main_category = active_categories.get("main") or {}
            main_category_name = self._clean_text(main_category.get("name")) or category_name
            grouped_products = (getir_listing.get("products") or {}).get("data") or []

            for group in grouped_products:
                subcategory_name = self._clean_text(group.get("name")) or main_category_name
                for product in group.get("products") or []:
                    offer = self._map_product(product, main_category_name, subcategory_name)
                    if offer is None or offer.source_product_id in seen_ids:
                        continue
                    seen_ids.add(offer.source_product_id)
                    offers.append(offer)
                    if len(offers) >= self.max_products:
                        return offers

        return offers

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(self._default_headers())
        return session

    def _build_scraper(self):
        if cloudscraper is None:
            return None
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "android", "mobile": True}
        )
        scraper.headers.update(self._default_headers())
        return scraper

    def _default_headers(self) -> dict:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Mobile Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"{self.base_url}/buyuk/",
        }

    def _discover_categories(self) -> Tuple[Tuple[str, str], ...]:
        prioritized = list(self._fallback_categories())
        seen_slugs = {slug for slug, _ in prioritized}
        soup = self._fetch_soup(f"{self.base_url}/buyuk/")
        if soup is None:
            return tuple(prioritized[: self.max_categories])

        state = self._state_from_soup(soup)
        if not state:
            return tuple(prioritized[: self.max_categories])

        category_rows = (
            (((state.get("getirListing") or {}).get("categories") or {}).get("data")) or []
        )
        for item in category_rows:
            slug = self._clean_text(item.get("slug"))
            name = self._clean_text(item.get("name"))
            if not slug or not name or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            prioritized.append((slug, name))
            if len(prioritized) >= self.max_categories:
                break
        return tuple(prioritized[: self.max_categories])

    @staticmethod
    def _fallback_categories() -> Tuple[Tuple[str, str], ...]:
        return (
            ("sut-urunleri-JGtfnNALTJ", "Sut Urunleri"),
            ("dondurma-Aw6YFhRWBI", "Dondurma"),
            ("meyve-sebze-VN2A9ap5Fm", "Meyve Sebze"),
            ("et-tavuk-balik-P1593VdPBd", "Et Tavuk Balik"),
            ("su-icecek-ewknEvzsJc", "Su Icecek"),
            ("atistirmalik-BaaxwkyV1y", "Atistirmalik"),
            ("temel-gida-IQH9bir3bX", "Temel Gida"),
            ("yiyecek-0VLJmBhnI3", "Pratik Yemek"),
            ("kahvalti-iat0l1yrkf", "Kahvaltilik"),
            ("firindan-q357eEdgBs", "Firindan"),
            ("fit-form-A9ciT987qU", "Fit Form"),
            ("ev-bakim-JXy6KcrPKW", "Ev Bakim"),
            ("ev-yasam-jdRnndEpyl", "Ev Yasam"),
            ("evcil-hayvan-T27vt8aM7c", "Evcil Hayvan"),
            ("kisisel-bakim-A21PNmddpt", "Kisisel Bakim"),
            ("bebek-T71m4N3D3K", "Bebek"),
            ("cinsel-saglik-viPc8mv9zd", "Cinsel Saglik"),
        )

    def _fetch_category_state(self, category_slug: str) -> Optional[dict]:
        soup = self._fetch_soup(f"{self.base_url}/buyuk/kategori/{category_slug}/")
        if soup is None:
            return None
        return self._state_from_soup(soup)

    def _fetch_soup(self, url: str) -> Optional[BeautifulSoup]:
        html = self._fetch_text(url)
        if not html:
            return None
        return BeautifulSoup(html, "html.parser")

    def _fetch_text(self, url: str) -> Optional[str]:
        for getter in (self._session_get_text, self._scraper_get_text):
            html = getter(url)
            if html and "__NEXT_DATA__" in html:
                return html
        return None

    def _session_get_text(self, url: str) -> Optional[str]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.request_timeout)
                if response.status_code == 200 and response.text:
                    return response.text
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _scraper_get_text(self, url: str) -> Optional[str]:
        if self.scraper is None:
            return None
        for _ in range(self.max_retries + 1):
            try:
                response = self.scraper.get(url, timeout=self.request_timeout)
                if response.status_code == 200 and response.text:
                    return response.text
            except requests.RequestException:
                continue
        return None

    @staticmethod
    def _state_from_soup(soup: BeautifulSoup) -> Optional[dict]:
        next_data = soup.find("script", {"id": "__NEXT_DATA__"})
        if next_data is None or not next_data.string:
            return None
        try:
            payload = json.loads(next_data.string)
        except json.JSONDecodeError:
            return None
        return (((payload.get("props") or {}).get("pageProps") or {}).get("initialState")) or None

    def _map_product(
        self,
        product: dict,
        main_category_name: str,
        subcategory_name: str,
    ) -> Optional[RawOffer]:
        product_id = self._clean_text(product.get("id"))
        name = self._clean_text(product.get("name"))
        price = self._coerce_price(product.get("price"))
        if not product_id or not name or price is None or price <= 0:
            return None

        brand = None
        if isinstance(product.get("brand"), dict):
            brand = self._clean_text(product["brand"].get("name"))

        image_url = self._clean_text(product.get("squareThumbnailURL"))
        if not image_url:
            for candidate in product.get("picURLs") or []:
                cleaned = self._clean_text(candidate)
                if cleaned:
                    image_url = cleaned
                    break

        product_slug = self._clean_text(product.get("slug"))
        product_url = None
        if product_slug:
            product_url = urljoin(self.base_url, f"/buyuk/urun/{product_slug}/")

        payload = {
            "main_category": main_category_name,
            "sub_category": subcategory_name,
            "product_url": product_url,
            "product": product,
        }

        return RawOffer(
            source_product_id=product_id,
            source_category=f"{main_category_name} / {subcategory_name}",
            source_name=name,
            source_brand=brand,
            source_size=self._clean_text(product.get("shortDescription")),
            listed_price=price,
            promo_price=None,
            stock_status=self._stock_status(product.get("status")),
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
            source_barcode=self._extract_barcode_candidates(product),
        )

    def _extract_barcode_candidates(self, product: dict) -> Optional[str]:
        for value in self._iter_barcode_values(product):
            cleaned = self._clean_text(value)
            if cleaned:
                return cleaned
        return None

    def _iter_barcode_values(self, value) -> Iterable[str]:
        if isinstance(value, dict):
            lower_keys = {str(key).lower(): key for key in value.keys()}
            direct_key = next(
                (
                    lower_keys[key]
                    for key in ("barcode", "barkod", "ean", "ean13", "gtin", "gtin13", "upc")
                    if key in lower_keys
                ),
                None,
            )
            if direct_key is not None:
                direct_value = value.get(direct_key)
                if isinstance(direct_value, (str, int, float)):
                    yield str(direct_value)

            label_value = None
            data_value = None
            for key, nested in value.items():
                normalized_key = str(key).lower()
                if normalized_key in {"label", "name", "title", "key"} and isinstance(nested, str):
                    label_value = nested.lower()
                if normalized_key in {"value", "content", "text", "description"} and isinstance(
                    nested, (str, int, float)
                ):
                    data_value = str(nested)
            if label_value and any(token in label_value for token in ("barkod", "barcode", "ean", "gtin", "upc")):
                if data_value:
                    yield data_value

            for nested in value.values():
                yield from self._iter_barcode_values(nested)
        elif isinstance(value, list):
            for item in value:
                yield from self._iter_barcode_values(item)

    @staticmethod
    def _stock_status(value: Optional[object]) -> str:
        if value == 1:
            return "in_stock"
        if value in {0, 2, 3}:
            return "out_of_stock"
        return "unknown"

    @staticmethod
    def _clean_text(value: Optional[object]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split()).strip()
        return cleaned or None

    @staticmethod
    def _coerce_price(value: Optional[object]) -> Optional[float]:
        if value in {None, ""}:
            return None
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None
