import json
from typing import List, Optional
from urllib.parse import urlencode

import requests

from .base import FetchContext, MarketAdapter, RawOffer


class RossmannAdapter(MarketAdapter):
    market_key = "rossmann_online"
    base_url = "https://www.rossmann.com.tr"
    category_id = 275
    page_size = 60
    image_prefix = "https://cdn.rossmann.com.tr/mnpadding/400/400/FFFFFF/media/catalog/product"

    def __init__(self, max_products: int = 9000, request_timeout: int = 20, max_retries: int = 1):
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
                "Referer": f"{self.base_url}/catalogsearch/result/?q=sampuan",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json,text/javascript,*/*;q=0.1",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        offset = 0
        total = None

        while total is None or offset < total:
            payload = self._fetch_page(offset)
            if payload is None:
                break

            product_payload = payload.get("product") or {}
            hits_wrapper = product_payload.get("hits") or {}
            total_info = hits_wrapper.get("total") or {}
            total = int(total_info.get("value") or 0)
            hits = hits_wrapper.get("hits") or []
            if not hits:
                break

            for hit in hits:
                offer = self._map_hit(hit)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers

            offset += len(hits)
        return offers

    def _fetch_page(self, offset: int) -> Optional[dict]:
        endpoint = f"{self.base_url}/elastic.php"
        params = {
            "categoryId": self.category_id,
            "order": "position",
            "direction": "desc",
            "size": self.page_size,
            "from": offset,
        }

        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                response = self.session.get(endpoint, params=params, timeout=self.request_timeout)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _map_hit(self, hit: dict) -> Optional[RawOffer]:
        source = hit.get("_source") or {}
        source_product_id = self._clean_text(str(source.get("entity_id") or source.get("id") or hit.get("_id")))
        name = self._clean_text(source.get("name"))
        if not source_product_id or not name:
            return None

        price = self._parse_price(source.get("price"))
        special_price = self._parse_price(source.get("special_price"))
        fallback_price = self._parse_price(source.get("crm_price"))
        current_price = special_price or price or fallback_price
        if current_price is None or current_price <= 0:
            return None

        listed_price = price if price and price > 0 else current_price
        promo_price = current_price if price and special_price and 0 < special_price < price else None
        brand = self._clean_text(source.get("brand") or source.get("branding"))
        size_label = self._clean_text(source.get("size") or source.get("freight"))
        stock_status = "in_stock" if int(source.get("is_in_stock") or 0) == 1 else "out_of_stock"
        image_url = self._image_url(source.get("image"))
        barcode = self._numeric_barcode(source.get("barcode"))
        category_name = self._category_name(source)
        product_url = self._product_url(source.get("url_key"))

        payload = {
            "url": product_url,
            "sku": source.get("sku"),
            "category_id": self.category_id,
        }

        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=brand,
            source_size=size_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=stock_status,
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
            source_barcode=barcode,
        )

    def _product_url(self, url_key: Optional[str]) -> Optional[str]:
        cleaned = self._clean_text(url_key)
        if not cleaned:
            return None
        return f"{self.base_url}/{cleaned}"

    def _image_url(self, image_path: Optional[str]) -> Optional[str]:
        cleaned = self._clean_text(image_path)
        if not cleaned:
            return None
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        if not cleaned.startswith("/"):
            cleaned = "/" + cleaned
        return f"{self.image_prefix}{cleaned}"

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

    @staticmethod
    def _numeric_barcode(value) -> Optional[str]:
        cleaned = RossmannAdapter._clean_text(value)
        if not cleaned:
            return None
        if cleaned.isdigit() and 8 <= len(cleaned) <= 14:
            return cleaned
        return None

    @staticmethod
    def _category_name(source: dict) -> str:
        breadcrumb = source.get("breadcrumb")
        if isinstance(breadcrumb, str):
            try:
                breadcrumb_items = json.loads(breadcrumb)
            except json.JSONDecodeError:
                breadcrumb_items = []
        elif isinstance(breadcrumb, list):
            breadcrumb_items = breadcrumb
        else:
            breadcrumb_items = []

        names = []
        for item in breadcrumb_items:
            if not isinstance(item, dict):
                continue
            name = RossmannAdapter._clean_text(item.get("name"))
            if name and name not in {"Tum Urunler", "Tüm Ürünler"}:
                names.append(name)
        if names:
            return names[-1]

        labels = source.get("paths_label")
        if isinstance(labels, list):
            cleaned = [RossmannAdapter._clean_text(value) for value in labels]
            filtered = [value for value in cleaned if value and value not in {"Tüm Ürünler"}]
            if filtered:
                return filtered[-1]
        return "Genel"
