import json
import subprocess
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from .base import FetchContext, MarketAdapter, RawOffer


class EvdeSiparisApiAdapter(MarketAdapter):
    market_key = "evdesiparis_api"
    api_base_url = "https://evdesiparis.com.tr/api"

    def __init__(self, per_page: int = 100, max_pages: int = 50, request_timeout: int = 15, max_retries: int = 1):
        self.per_page = per_page
        self.max_pages = max_pages
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Referer": "https://evdesiparis.com/store",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        for page in range(1, self.max_pages + 1):
            payload = self._fetch_page(page)
            if payload is None:
                continue

            products = payload.get("data") or []
            if not isinstance(products, list) or not products:
                break

            for product in products:
                offer = self._map_product(product)
                if offer is not None:
                    offers.append(offer)

            meta = payload.get("meta") or {}
            last_page = self._coerce_int(meta.get("last_page")) or page
            if page >= last_page or len(products) < self.per_page:
                break
        return offers

    def _fetch_page(self, page: int) -> Optional[Dict[str, Any]]:
        endpoint = f"{self.api_base_url}/products"
        params = {"page": page, "per_page": self.per_page, "sort_by": "name", "sort_order": "asc"}
        response = self._safe_get(endpoint, params=params)
        if response is not None:
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return None
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

    def _curl_json(self, url: str, params: dict) -> Optional[Dict[str, Any]]:
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
                if isinstance(payload, dict):
                    return payload
        return None

    def _map_product(self, product: Dict[str, Any]) -> Optional[RawOffer]:
        name = product.get("name")
        current_price = self._coerce_price(product.get("current_price"))
        if not name or current_price is None or current_price <= 0:
            return None

        listed_price = current_price
        promo_price = None
        campaign = product.get("campaign") or {}
        campaign_price = self._coerce_price(campaign.get("campaign_price"))
        original_price = self._coerce_price(campaign.get("original_price"))
        if campaign_price is not None and original_price is not None and campaign_price < original_price:
            listed_price = original_price
            promo_price = campaign_price

        category = product.get("category") or {}
        source_category = category.get("name") or "Genel"
        image_url = self._image_url(product)
        source_brand = self._brand_name(product)
        source_size = self._source_size(product)

        return RawOffer(
            source_product_id=str(product.get("id")),
            source_category=source_category,
            source_name=name,
            source_brand=source_brand,
            source_size=source_size,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=str(product.get("stock_status") or "unknown"),
            image_url=image_url,
            payload_json=json.dumps(product, ensure_ascii=True),
        )

    @staticmethod
    def _brand_name(product: Dict[str, Any]) -> Optional[str]:
        brand = product.get("brand")
        if isinstance(brand, dict):
            return brand.get("name")
        if isinstance(brand, str):
            return brand or None
        return None

    @staticmethod
    def _source_size(product: Dict[str, Any]) -> Optional[str]:
        unit_code = (product.get("unit_code") or "").strip()
        content = product.get("content")
        package_quantity = product.get("package_quantity")

        quantity = None
        if package_quantity not in {None, "", "0.0000"}:
            quantity = str(package_quantity).rstrip("0").rstrip(".")
        elif content not in {None, "", "0.0000"}:
            quantity = str(content).rstrip("0").rstrip(".")

        if quantity and unit_code and unit_code != "Ad":
            return f"{quantity} {unit_code}"
        if unit_code:
            return unit_code
        return None

    @staticmethod
    def _image_url(product: Dict[str, Any]) -> Optional[str]:
        primary_image = product.get("primary_image")
        if isinstance(primary_image, list) and primary_image:
            full_url = primary_image[0].get("full_url")
            if full_url:
                return str(full_url)

        images = product.get("images")
        if isinstance(images, list) and images:
            full_url = images[0].get("full_url")
            if full_url:
                return str(full_url)

        return None

    @staticmethod
    def _coerce_price(value: Any) -> Optional[float]:
        if value in {None, ""}:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value in {None, ""}:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class EvdesiparisSanliurfaAdapter(EvdeSiparisApiAdapter):
    market_key = "evdesiparis_sanliurfa"
