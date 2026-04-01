import json
from typing import Dict, List, Optional

import requests

from .base import FetchContext, MarketAdapter, RawOffer


class A101KapidaAdapter(MarketAdapter):
    market_key = "a101_kapida"
    search_url = "https://a101.wawlabs.com/search"

    def __init__(
        self,
        max_products: int = 1200,
        request_timeout: int = 20,
        max_retries: int = 1,
    ) -> None:
        self.max_products = max_products
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://a101.com.tr/kapida/",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        payload = self._fetch_search_payload()
        products = payload.get("res") if isinstance(payload, dict) else None
        if not isinstance(products, list):
            return []

        offers: List[RawOffer] = []
        seen_ids = set()
        for product in products:
            if not isinstance(product, dict):
                continue
            offer = self._map_product(product)
            if offer is None or offer.source_product_id in seen_ids:
                continue
            seen_ids.add(offer.source_product_id)
            offers.append(offer)
            if len(offers) >= self.max_products:
                break
        return offers

    def _fetch_search_payload(self) -> Optional[dict]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    self.search_url,
                    params={"q": "*"},
                    timeout=self.request_timeout,
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, json.JSONDecodeError) as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _map_product(self, product: Dict[str, object]) -> Optional[RawOffer]:
        product_id = self._clean_text(product.get("id"))
        name = self._clean_text(product.get("title"))
        current_price = self._coerce_price(product.get("price"))
        if not product_id or not name or current_price is None or current_price <= 0:
            return None

        old_price = self._coerce_price(product.get("old_price"))
        listed_price = old_price if old_price and old_price > current_price else current_price

        promotion_price = self._promotion_price(product.get("promotion"))
        promo_price = promotion_price if promotion_price and promotion_price < listed_price else None

        return RawOffer(
            source_product_id=product_id,
            source_category=(
                self._clean_text(product.get("category_org"))
                or self._clean_text(product.get("category"))
                or "Genel"
            ),
            source_name=name,
            source_brand=self._brand_from_name(name),
            source_size=self._source_size(product),
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="in_stock" if bool(product.get("available")) else "out_of_stock",
            image_url=self._image_url(product.get("image")),
            payload_json=json.dumps(product, ensure_ascii=True),
            source_barcode=None,
        )

    @staticmethod
    def _promotion_price(value: object) -> Optional[float]:
        if not isinstance(value, list):
            return None
        best_price: Optional[float] = None
        for item in value:
            if not isinstance(item, dict):
                continue
            discounted = A101KapidaAdapter._coerce_price(item.get("discountedPrice"))
            if discounted is None or discounted <= 0:
                continue
            if best_price is None or discounted < best_price:
                best_price = discounted
        return best_price

    @staticmethod
    def _image_url(value: object) -> Optional[str]:
        if not isinstance(value, list):
            return None
        fallback: Optional[str] = None
        for item in value:
            if not isinstance(item, dict):
                continue
            image_url = A101KapidaAdapter._clean_text(item.get("url"))
            if not image_url:
                continue
            if fallback is None:
                fallback = image_url
            if item.get("imageType") == "product":
                return image_url
        return fallback

    @staticmethod
    def _source_size(product: Dict[str, object]) -> Optional[str]:
        sales_unit = A101KapidaAdapter._clean_text(product.get("salesUnitOfMeasure"))
        base_unit = A101KapidaAdapter._clean_text(product.get("baseUnitOfMeasure"))
        if sales_unit and base_unit and sales_unit != base_unit:
            return f"{sales_unit}/{base_unit}"
        return sales_unit

    @staticmethod
    def _brand_from_name(name: str) -> Optional[str]:
        first_token = name.split()[0].strip()
        if len(first_token) <= 1 or first_token[0].isdigit():
            return None
        return first_token.title()

    @staticmethod
    def _coerce_price(value: object) -> Optional[float]:
        if value in {None, ""}:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric > 999:
            return round(numeric / 100.0, 2)
        return round(numeric, 2)

    @staticmethod
    def _clean_text(value: object) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None
