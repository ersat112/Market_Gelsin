import json
import subprocess
from urllib.parse import urlencode
from typing import List, Optional

import requests

from .base import FetchContext, MarketAdapter, RawOffer


class WooCommerceStoreApiAdapter(MarketAdapter):
    market_key = "woocommerce"
    base_url = ""

    def __init__(self, per_page: int = 100, max_pages: int = 20, request_timeout: int = 15, max_retries: int = 1):
        self.per_page = per_page
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
            if len(products) < self.per_page:
                break
        return offers

    def _fetch_page(self, page: int) -> Optional[List[dict]]:
        endpoint = f"{self.base_url}/wp-json/wc/store/products"
        params = {"page": page, "per_page": self.per_page}
        response = self._safe_get(endpoint, params=params)
        if response is not None:
            response.raise_for_status()
            return response.json()
        return self._curl_json(endpoint, params=params)

    def _safe_get(self, url: str, params: Optional[dict] = None) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                return self.session.get(url, params=params, timeout=self.request_timeout)
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _curl_json(self, url: str, params: dict) -> Optional[List[dict]]:
        query = urlencode(params)
        full_url = f"{url}?{query}" if query else url
        for _ in range(self.max_retries + 1):
            completed = subprocess.run(
                [
                    "curl",
                    "-L",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    str(self.request_timeout),
                    "--url",
                    full_url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0:
                try:
                    payload = json.loads(completed.stdout)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, list):
                    return payload
                continue
        return None

    def _map_product(self, product: dict) -> Optional[RawOffer]:
        name = product.get("name")
        prices = product.get("prices") or {}
        current_price = self._minor_to_price(prices.get("price"), prices.get("currency_minor_unit"))
        regular_price = self._minor_to_price(prices.get("regular_price"), prices.get("currency_minor_unit"))
        sale_price = self._minor_to_price(prices.get("sale_price"), prices.get("currency_minor_unit"))

        if not name or current_price is None:
            return None

        listed_price = regular_price if regular_price and regular_price >= current_price else current_price
        promo_price = current_price if listed_price > current_price else None

        categories = product.get("categories") or []
        images = product.get("images") or []

        return RawOffer(
            source_product_id=str(product.get("id")),
            source_category=categories[0].get("name", "Genel") if categories else "Genel",
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price if promo_price != sale_price or promo_price is not None else sale_price,
            stock_status="in_stock" if product.get("is_in_stock") else "out_of_stock",
            image_url=images[0].get("src") if images else None,
            payload_json=json.dumps(product, ensure_ascii=True),
        )

    @staticmethod
    def _minor_to_price(raw_value: Optional[str], minor_unit: Optional[int]) -> Optional[float]:
        if raw_value in {None, ""}:
            return None
        try:
            divisor = 10 ** int(minor_unit or 0)
            return float(raw_value) / divisor
        except Exception:
            return None


class BalikesirSanalMarketAdapter(WooCommerceStoreApiAdapter):
    market_key = "balikesir_sanal_market"
    base_url = "https://balikesirsanalmarket.com"


class AmasyaEtUrunleriAdapter(WooCommerceStoreApiAdapter):
    market_key = "amasya_et_urunleri_market_amasya"
    base_url = "https://market.amasyaeturunleri.com.tr"


class AtilimSanalMarketAdapter(WooCommerceStoreApiAdapter):
    market_key = "atilim_sanal_market_sakarya"
    base_url = "https://www.atilimsanalmarket.com"


class IsikMarketAdapter(WooCommerceStoreApiAdapter):
    market_key = "isik_market_elazig"
    base_url = "https://isikmarket.com.tr"
