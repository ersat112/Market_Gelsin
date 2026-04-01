import json
import re
from typing import List, Optional, Tuple

import requests

from .base import FetchContext, MarketAdapter, RawOffer


class KozmelaAdapter(MarketAdapter):
    market_key = "kozmela_online"
    base_url = "https://www.kozmela.com"
    collection_paths: Tuple[str, ...] = (
        "/populer-urunler",
        "/kozmela-outlet",
        "/avantajli-setler",
    )

    def __init__(self, max_products: int = 3000, request_timeout: int = 20, max_retries: int = 1):
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
                "Referer": self.base_url,
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()

        for path in self._collection_paths():
            html_text = self._fetch_text(path)
            if not html_text:
                continue
            category_name = self._category_name(html_text)
            for product in self._extract_products(html_text):
                offer = self._map_product(product, category_name)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _collection_paths(self) -> Tuple[str, ...]:
        html_text = self._fetch_text("/")
        if not html_text:
            return self.collection_paths

        discovered: List[str] = []
        for href in re.findall(r'href=[\"\'](/[^\"\']+)[\"\']', html_text):
            normalized = href.split("?", 1)[0].rstrip("/")
            if not normalized or normalized == "/":
                continue
            if normalized.startswith(("/account", "/cart", "/pages", "/blogs", "/collections", "/policies", "/search")):
                continue
            if normalized not in discovered:
                discovered.append(normalized)
            if len(discovered) >= 24:
                break

        if not discovered:
            return self.collection_paths

        merged = list(self.collection_paths)
        for path in discovered:
            if path not in merged:
                merged.append(path)
        return tuple(merged)

    def _fetch_text(self, path: str) -> Optional[str]:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.request_timeout)
                response.raise_for_status()
                return response.text
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _extract_products(self, html_text: str) -> List[dict]:
        products: List[dict] = []
        for raw in re.findall(r"PRODUCT_DATA\.push\(JSON\.parse\('(.*?)'\)\)", html_text, re.S):
            try:
                decoded = bytes(raw, "utf-8").decode("unicode_escape")
                product = json.loads(decoded)
            except Exception:
                continue
            if isinstance(product, dict):
                products.append(product)
        return products

    def _category_name(self, html_text: str) -> str:
        match = re.search(r"CATEGORY_DATA = JSON\.parse\('(.*?)'\);", html_text, re.S)
        if not match:
            return "Genel"
        try:
            decoded = bytes(match.group(1), "utf-8").decode("unicode_escape")
            payload = json.loads(decoded)
        except Exception:
            return "Genel"
        return self._clean_text(payload.get("name")) or "Genel"

    def _map_product(self, product: dict, fallback_category: str) -> Optional[RawOffer]:
        source_product_id = self._clean_text(product.get("id"))
        name = self._clean_text(product.get("name"))
        if not source_product_id or not name:
            return None

        listed_price = self._parse_price(product.get("total_base_price"))
        current_price = self._parse_price(product.get("total_sale_price")) or self._parse_price(product.get("sale_price"))
        if current_price is None or current_price <= 0:
            return None
        if listed_price is None or listed_price <= 0:
            listed_price = current_price

        promo_price = current_price if listed_price > current_price else None
        quantity = int(product.get("quantity") or 0)
        stock_status = "in_stock" if quantity > 0 else "out_of_stock"
        barcode = self._barcode(product)
        image_url = self._clean_text(product.get("image"))
        category_name = self._clean_text(product.get("category")) or fallback_category
        size_label = self._clean_text(product.get("model"))
        product_url = self._product_url(product.get("url"))

        payload = {
            "url": product_url,
            "brand": product.get("brand"),
            "category_id": product.get("category_id"),
        }

        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=self._clean_text(product.get("brand")),
            source_size=size_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=stock_status,
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
            source_barcode=barcode,
        )

    def _product_url(self, value) -> Optional[str]:
        cleaned = self._clean_text(value)
        if not cleaned:
            return None
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        if not cleaned.startswith("/"):
            cleaned = "/" + cleaned
        return f"{self.base_url}{cleaned}"

    def _barcode(self, product: dict) -> Optional[str]:
        for key in ("code", "supplier_code"):
            cleaned = self._clean_text(product.get(key))
            if cleaned and cleaned.isdigit() and 8 <= len(cleaned) <= 14:
                return cleaned
        return None

    @staticmethod
    def _parse_price(value) -> Optional[float]:
        if value in {None, ""}:
            return None
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _clean_text(value) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split()).strip()
        return cleaned or None
