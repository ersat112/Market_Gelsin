import json
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import FetchContext, MarketAdapter, RawOffer


class MigrosAdapter(MarketAdapter):
    market_key = "migros_sanal_market"
    base_url = "https://www.migros.com.tr"

    def __init__(
        self,
        max_products: int = 1500,
        max_categories: int = 18,
        max_pages_per_category: int = 20,
        request_timeout: int = 20,
        max_retries: int = 1,
    ):
        self.max_products = max_products
        self.max_categories = max_categories
        self.max_pages_per_category = max_pages_per_category
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{self.base_url}/",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_slug in self._discover_category_slugs():
            page_count = 1
            for page in range(1, self.max_pages_per_category + 1):
                payload = self._fetch_category_page(category_slug=category_slug, page=page)
                if payload is None:
                    break
                search_info = payload.get("data", {}).get("searchInfo", {}) if isinstance(payload, dict) else {}
                store_product_infos = search_info.get("storeProductInfos") or []
                if not store_product_infos:
                    break
                page_count = int(search_info.get("pageCount") or 1)
                for product in store_product_infos:
                    offer = self._map_product(product)
                    if offer is None or offer.source_product_id in seen_ids:
                        continue
                    seen_ids.add(offer.source_product_id)
                    offers.append(offer)
                    if len(offers) >= self.max_products:
                        return offers
                if page >= page_count:
                    break
        return offers

    def _discover_category_slugs(self) -> Tuple[str, ...]:
        response = self._safe_get(f"{self.base_url}/")
        if response is None:
            return self._fallback_category_slugs()

        response.raise_for_status()
        slugs: List[str] = []
        for match in re.findall(r"([a-z0-9-]+-c-[a-z0-9]+)", response.text):
            slug = match
            if slug.startswith("home-page-category-card-"):
                slug = slug.replace("home-page-category-card-", "", 1)
            if slug not in slugs:
                slugs.append(slug)
            if len(slugs) >= self.max_categories:
                break
        return tuple(slugs or self._fallback_category_slugs())

    @staticmethod
    def _fallback_category_slugs() -> Tuple[str, ...]:
        return (
            "meyve-sebze-c-2",
            "et-tavuk-balik-c-3",
            "sut-kahvaltilik-c-4",
            "temel-gida-c-5",
            "icecek-c-6",
            "atistirmalik-c-113fb",
            "deterjan-temizlik-c-7",
            "kisisel-bakim-kozmetik-saglik-c-8",
        )

    def _fetch_category_page(self, category_slug: str, page: int) -> Optional[dict]:
        endpoint = f"{self.base_url}/rest/search/screens/{category_slug}"
        params = {"reid": "1"}
        if page > 1:
            params["page"] = str(page)
        response = self._safe_get(endpoint, params=params, referer=f"{self.base_url}/{category_slug}")
        if response is None:
            return None
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError:
            return None

    def _safe_get(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
    ) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        headers = {}
        if referer:
            headers["Referer"] = referer
        for _ in range(self.max_retries + 1):
            try:
                return self.session.get(url, params=params, headers=headers, timeout=self.request_timeout)
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _map_product(self, product: dict) -> Optional[RawOffer]:
        sku = self._clean_text(product.get("sku"))
        name = self._clean_text(product.get("name"))
        if not sku or not name:
            return None

        shown_price = self._coerce_price(product.get("shownPrice"))
        regular_price = self._coerce_price(product.get("regularPrice"))
        if shown_price is None or shown_price <= 0:
            return None

        listed_price = regular_price if regular_price and regular_price > shown_price else shown_price
        promo_price = shown_price if listed_price > shown_price else None

        category = self._clean_text((product.get("category") or {}).get("name")) or "Genel"
        brand = self._clean_text((product.get("brand") or {}).get("name"))
        image_url = self._image_url(product)
        stock_status = "in_stock" if str(product.get("status") or "").upper() == "IN_SALE" else "unknown"
        size_label = self._size_label(product)
        product_url = self._product_url(product)

        payload = {
            "id": product.get("id"),
            "sku": sku,
            "prettyName": product.get("prettyName"),
            "category": category,
            "brand": brand,
            "status": product.get("status"),
            "unit": product.get("unit"),
            "unitAmount": product.get("unitAmount"),
            "shownPrice": product.get("shownPrice"),
            "regularPrice": product.get("regularPrice"),
            "productUrl": product_url,
        }

        return RawOffer(
            source_product_id=sku,
            source_category=category,
            source_name=name,
            source_brand=brand,
            source_size=size_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=stock_status,
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
            source_barcode=None,
        )

    def _product_url(self, product: dict) -> Optional[str]:
        pretty_name = self._clean_text(product.get("prettyName"))
        if not pretty_name:
            return None
        return urljoin(self.base_url, f"/{pretty_name}")

    @staticmethod
    def _image_url(product: dict) -> Optional[str]:
        images = product.get("images") or []
        for image in images:
            urls = image.get("urls") if isinstance(image, dict) else None
            if not isinstance(urls, dict):
                continue
            for key in ("PRODUCT_DETAIL", "PRODUCT_HD", "PRODUCT_LIST", "CART"):
                value = urls.get(key)
                if value:
                    return value
        return None

    @staticmethod
    def _size_label(product: dict) -> Optional[str]:
        unit = MigrosAdapter._clean_text(product.get("unit"))
        unit_amount = product.get("unitAmount")
        if unit and unit_amount:
            return f"{unit_amount} {unit}"
        return unit

    @staticmethod
    def _clean_text(value: Optional[object]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None

    @staticmethod
    def _coerce_price(value: Optional[object]) -> Optional[float]:
        if value in {None, ""}:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric > 999:
            return round(numeric / 100.0, 2)
        return round(numeric, 2)
