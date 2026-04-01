import json
import subprocess
from typing import List, Optional
from urllib.parse import urlencode

import requests

from .base import FetchContext, MarketAdapter, RawOffer


class ShopifyJsonAdapter(MarketAdapter):
    market_key = "shopify"
    base_url = ""
    verify_ssl = True

    def __init__(self, limit: int = 40, max_pages: int = 2, request_timeout: int = 15, max_retries: int = 1):
        self.limit = limit
        self.max_pages = max_pages
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
                "Accept": "application/json,text/javascript,*/*;q=0.1",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        for page in range(1, self.max_pages + 1):
            products = self._fetch_page(page)
            if products is None:
                continue
            if not products:
                break
            for product in products:
                offer = self._map_product(product)
                if offer is not None:
                    offers.append(offer)
            if len(products) < self.limit:
                break
        return offers

    def _fetch_page(self, page: int) -> Optional[List[dict]]:
        endpoint = f"{self.base_url}/products.json"
        params = {"limit": self.limit, "page": page}
        response = self._safe_get(endpoint, params=params)
        if response is not None:
            response.raise_for_status()
            payload = response.json() or {}
            return payload.get("products") or []
        return self._curl_json(endpoint, params=params)

    def _safe_get(self, url: str, params: Optional[dict] = None) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                return self.session.get(url, params=params, timeout=self.request_timeout, verify=self.verify_ssl)
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _curl_json(self, url: str, params: dict) -> Optional[List[dict]]:
        query = urlencode(params)
        full_url = f"{url}?{query}" if query else url
        command = [
            "curl",
            "-L",
            "--silent",
            "--show-error",
            "--max-time",
            str(self.request_timeout),
            "--url",
            full_url,
        ]
        if not self.verify_ssl:
            command.insert(1, "-k")

        for _ in range(self.max_retries + 1):
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                continue
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload.get("products") or []
        return None

    def _map_product(self, product: dict) -> Optional[RawOffer]:
        variants = product.get("variants") or []
        available_variants = [variant for variant in variants if variant.get("available")]
        chosen_variant = (available_variants or variants or [None])[0]
        if chosen_variant is None:
            return None

        current_price = self._parse_price(chosen_variant.get("price"))
        compare_at_price = self._parse_price(chosen_variant.get("compare_at_price"))
        if current_price is None or current_price <= 0:
            return None

        listed_price = compare_at_price if compare_at_price and compare_at_price > current_price else current_price
        promo_price = current_price if compare_at_price and compare_at_price > current_price else None

        category = self._extract_category(product)
        brand = self._clean_optional_text(product.get("vendor"))
        variant_title = self._clean_optional_text(chosen_variant.get("title"))
        size_label = None if variant_title == "Default Title" else variant_title
        image_url = ((product.get("images") or [{}])[0]).get("src")
        stock_status = "in_stock" if available_variants else "out_of_stock"

        return RawOffer(
            source_product_id=self._clean_optional_text(chosen_variant.get("sku")) or str(product.get("id")),
            source_category=category,
            source_name=product.get("title") or "",
            source_brand=brand,
            source_size=size_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=stock_status,
            image_url=image_url,
            payload_json=json.dumps(product, ensure_ascii=True),
            source_barcode=self._clean_optional_text(chosen_variant.get("barcode")),
        )

    @staticmethod
    def _extract_category(product: dict) -> str:
        raw_tags = product.get("tags") or []
        tags = [tag.strip() for tag in raw_tags.split(",")] if isinstance(raw_tags, str) else raw_tags
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("cat:"):
                category = tag.split(":", 1)[1].replace("-", " ").strip()
                if category:
                    return category.title()
        product_type = product.get("product_type")
        if isinstance(product_type, str) and product_type.strip():
            return product_type.strip()
        return "Genel"

    @staticmethod
    def _clean_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _parse_price(value: Optional[str]) -> Optional[float]:
        if value in {None, ""}:
            return None
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            return None


class BatmanSanalMarketAdapter(ShopifyJsonAdapter):
    market_key = "batman_sanal_market"
    base_url = "https://batmansanalmarket.com"


class BingolMarketAdapter(ShopifyJsonAdapter):
    market_key = "bingol_market_bingol"
    base_url = "https://bingolmarket.com"
    verify_ssl = False


class EveShopAdapter(ShopifyJsonAdapter):
    market_key = "eveshop_online"
    base_url = "https://www.eveshop.com.tr"

    def __init__(self):
        super().__init__(limit=250, max_pages=40, request_timeout=20, max_retries=2)
