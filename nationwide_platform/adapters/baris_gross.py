import json
import math
from typing import Dict, Iterable, List, Optional

import requests

from .base import FetchContext, MarketAdapter, RawOffer


class BarisGrossAdapter(MarketAdapter):
    market_key = "baris_gross_izmir"
    base_url = "https://api.barisgrossonlinemagaza.com/api"

    def __init__(
        self,
        per_page: int = 25,
        max_pages_per_category: int = 40,
        max_products: int = 5000,
        request_timeout: int = 20,
        max_retries: int = 1,
    ) -> None:
        self.per_page = per_page
        self.max_pages_per_category = max_pages_per_category
        self.max_products = max_products
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
                "Referer": "https://barisgrossonlinemagaza.com/",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category in self._fetch_categories():
            slug = category.get("slug")
            title = category.get("title") or "Genel"
            product_count = self._to_int(category.get("productCount")) or 0
            if not isinstance(slug, str) or not slug:
                continue
            page_limit = max(1, math.ceil(product_count / self.per_page)) if product_count else 1
            for page in range(1, min(page_limit, self.max_pages_per_category) + 1):
                cards = self._fetch_category_page(slug, page)
                if not cards:
                    break
                for card in cards:
                    offer = self._map_product_card(card, title)
                    if offer is None or offer.source_product_id in seen_ids:
                        continue
                    seen_ids.add(offer.source_product_id)
                    offers.append(offer)
                    if len(offers) >= self.max_products:
                        return offers
        return offers

    def _fetch_categories(self) -> List[dict]:
        response = self._safe_get("/categories")
        if response is None:
            return []
        response.raise_for_status()
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return []
        categories = payload.get("categories")
        return categories if isinstance(categories, list) else []

    def _fetch_category_page(self, slug: str, page_number: int) -> List[dict]:
        headers = {"x-encoded-url": slug}
        if page_number > 1:
            headers["x-page-number"] = str(page_number)
        response = self._safe_get(f"/home/slug/{slug}", headers=headers)
        if response is None:
            return []
        response.raise_for_status()
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return []

        cards: List[dict] = []
        for node in self._walk(payload):
            if isinstance(node, dict) and node.get("component") == "product-list":
                products = node.get("products")
                if isinstance(products, list):
                    cards.extend(product for product in products if isinstance(product, dict))
        return cards

    def _safe_get(self, path: str, headers: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
        url = f"{self.base_url}{path}"
        merged_headers = dict(self.session.headers)
        if headers:
            merged_headers.update(headers)

        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                return self.session.get(url, headers=merged_headers, timeout=self.request_timeout)
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _map_product_card(self, card: dict, category_name: str) -> Optional[RawOffer]:
        product = card.get("product")
        if not isinstance(product, dict):
            return None

        source_product_id = product.get("id")
        name = product.get("name")
        current_price = self._to_float(product.get("price"))
        old_price = self._to_float(product.get("oldPrice"))
        if source_product_id in {None, ""} or not isinstance(name, str) or current_price is None or current_price <= 0:
            return None

        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if listed_price > current_price else None
        size_label = self._size_label(product)
        barcode = product.get("barcode")
        if isinstance(barcode, str):
            barcode = barcode.strip() or None
        else:
            barcode = None

        return RawOffer(
            source_product_id=str(source_product_id),
            source_category=category_name,
            source_name=" ".join(name.split()),
            source_brand=None,
            source_size=size_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="out_of_stock" if product.get("outOfStock") else "in_stock",
            image_url=self._clean_string(product.get("imageUrl")),
            payload_json=json.dumps(product, ensure_ascii=True),
            source_barcode=barcode,
        )

    @staticmethod
    def _walk(node: object) -> Iterable[object]:
        stack = [node]
        while stack:
            current = stack.pop()
            yield current
            if isinstance(current, dict):
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)

    @staticmethod
    def _to_float(value: object) -> Optional[float]:
        if value in {None, ""}:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: object) -> Optional[int]:
        if value in {None, ""}:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_string(value: object) -> Optional[str]:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _size_label(product: dict) -> Optional[str]:
        package_weight = product.get("packageWeight")
        unit_code = product.get("unitCode")
        if package_weight in {None, "", 0, 0.0} or not isinstance(unit_code, str):
            return None
        try:
            value = float(package_weight)
        except (TypeError, ValueError):
            return None
        if value == 1.0 and unit_code.strip().lower() == "adet":
            return None
        if value.is_integer():
            return f"{int(value)} {unit_code.strip()}"
        return f"{value:g} {unit_code.strip()}"
