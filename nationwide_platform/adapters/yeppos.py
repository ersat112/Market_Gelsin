import json
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin

import requests

from .base import FetchContext, MarketAdapter, RawOffer


class YepPosMenuProductsAdapter(MarketAdapter):
    market_key = "yeppos_menu_products"
    base_url = ""

    def __init__(self, max_products: int = 5000, request_timeout: int = 15, max_retries: int = 1):
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
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        branch_id, order_type, branch_payload = self._resolve_branch()
        if branch_id is None or order_type is None:
            return []

        menu_payload = self._fetch_menu_products(branch_id, order_type)
        products = ((menu_payload or {}).get("data") or {}).get("products") or []

        offers: List[RawOffer] = []
        seen_ids = set()
        for product in products:
            offer = self._parse_product(product, branch_id=branch_id, order_type=order_type, branch_payload=branch_payload)
            if offer is None or offer.source_product_id in seen_ids:
                continue
            seen_ids.add(offer.source_product_id)
            offers.append(offer)
            if len(offers) >= self.max_products:
                break
        return offers

    def _resolve_branch(self) -> Tuple[Optional[int], Optional[str], Dict]:
        payload = self._safe_get_json(self._ajax_url("header.php", {"lang": "tr"}))
        app = ((payload or {}).get("data") or {}).get("app") or {}
        branches = app.get("branches") or []
        if not branches:
            return None, None, {}

        default_branch_id = app.get("defaultBranchId")
        branch_payload = next(
            (branch for branch in branches if branch.get("id") == default_branch_id),
            branches[0],
        )
        branch_id = branch_payload.get("id")
        if branch_id is None:
            return None, None, {}

        order_type = self._select_order_type(branch_payload.get("orderTypes") or {})
        return int(branch_id), order_type, branch_payload

    def _fetch_menu_products(self, branch_id: int, order_type: str) -> Optional[Dict]:
        params = {
            "branch_id": branch_id,
            "order_type": order_type,
            "lang": "tr",
        }
        return self._safe_get_json(self._ajax_url("menu-products.php", params))

    def _parse_product(self, product: Dict, branch_id: int, order_type: str, branch_payload: Dict) -> Optional[RawOffer]:
        product_id = product.get("id")
        name = self._clean_optional_text(product.get("name"))
        current_price = self._to_float(product.get("basePrice"))
        if product_id is None or not name or current_price is None or current_price <= 0:
            return None

        old_price = self._to_float(product.get("oldPrice"))
        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None

        payload = {
            "branch_id": branch_id,
            "order_type": order_type,
            "branch": branch_payload,
            "product": product,
        }

        return RawOffer(
            source_product_id=str(product_id),
            source_category=self._clean_optional_text(product.get("categoryName")) or "Genel",
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="unknown",
            image_url=self._image_url(product),
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    def _ajax_url(self, endpoint: str, params: Dict[str, object]) -> str:
        query = urlencode(params)
        return urljoin(self.base_url, f"/yeppanel/db/ajax/web/{endpoint}?{query}")

    def _safe_get_json(self, url: str) -> Optional[Dict]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.request_timeout)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    @staticmethod
    def _select_order_type(order_types: Dict[str, bool]) -> Optional[str]:
        for candidate in ("delivery", "takeaway", "tableOrder", "tableMenu"):
            if order_types.get(candidate):
                return candidate
        return None

    def _image_url(self, product: Dict) -> Optional[str]:
        media = product.get("media") or []
        for item in media:
            image_url = self._clean_optional_text((item or {}).get("url"))
            if image_url:
                return urljoin(self.base_url, image_url)
        image_url = self._clean_optional_text(product.get("image"))
        if image_url:
            return urljoin(self.base_url, image_url)
        return None

    @staticmethod
    def _clean_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        return cleaned or None

    @staticmethod
    def _to_float(value: object) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            return None


class KuzeyMarketAdapter(YepPosMenuProductsAdapter):
    market_key = "kuzey_market_izmir"
    base_url = "https://kuzeymarket.com.tr"
