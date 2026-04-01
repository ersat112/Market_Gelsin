import html
import json
import re
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import FetchContext, MarketAdapter, RawOffer


class MagentoAutocompleteAdapter(MarketAdapter):
    market_key = "magento_autocomplete"
    base_url = ""
    autocomplete_path = "/mageworx_searchsuiteautocomplete/ajax/index/"
    seed_queries: Tuple[str, ...] = ("domates", "peynir", "sut", "makarna")

    def __init__(self, max_products: int = 40, request_timeout: int = 20, max_retries: int = 1):
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
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                "Referer": self.base_url,
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        self._safe_get(self.base_url)
        for query in self.seed_queries:
            response = self._safe_get(
                urljoin(self.base_url, self.autocomplete_path),
                params={"q": query},
            )
            if response is None:
                continue
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError:
                continue
            for entry in self._product_entries(payload):
                offer = self._map_entry(entry, query)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

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

    @staticmethod
    def _product_entries(payload: dict) -> Iterable[dict]:
        for block in payload.get("result") or []:
            if block.get("code") == "product":
                return block.get("data") or []
        return []

    def _map_entry(self, entry: dict, query: str) -> Optional[RawOffer]:
        name = self._clean_text(entry.get("name"))
        if not name:
            return None

        product_id = ((entry.get("add_to_cart") or {}).get("productId")) or self._product_id_from_url(entry.get("url"))
        if product_id is None:
            return None

        listed_price, promo_price = self._parse_price_html(entry.get("price", ""))
        if listed_price is None or listed_price <= 0:
            return None

        payload = dict(entry)
        payload["seed_query"] = query

        return RawOffer(
            source_product_id=str(product_id),
            source_category="Genel",
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=self._stock_status(entry),
            image_url=entry.get("image"),
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _clean_text(text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        cleaned = " ".join(text.split())
        return cleaned or None

    @staticmethod
    def _product_id_from_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        match = re.search(r"/product/(\d+)/", url)
        if match:
            return match.group(1)
        slug = url.rstrip("/").split("/")[-1]
        return slug or None

    @staticmethod
    def _stock_status(entry: dict) -> str:
        text = " ".join(
            [
                str(entry.get("name", "")),
                str(entry.get("price", "")),
                json.dumps(entry.get("add_to_cart") or {}, ensure_ascii=True),
            ]
        ).lower()
        if "stokta yok" in text or "out of stock" in text:
            return "out_of_stock"
        return "unknown"

    @staticmethod
    def _parse_price_html(price_html: str) -> Tuple[Optional[float], Optional[float]]:
        if not price_html:
            return None, None
        soup = BeautifulSoup(html.unescape(price_html), "html.parser")
        amounts = []
        for node in soup.select("[data-price-amount]"):
            raw_amount = node.get("data-price-amount")
            if raw_amount in {None, ""}:
                continue
            try:
                amounts.append(float(str(raw_amount).replace(",", ".")))
            except ValueError:
                continue
        if not amounts:
            text = soup.get_text(" ", strip=True)
            amounts = MagentoAutocompleteAdapter._extract_numbers(text)
        if not amounts:
            return None, None
        current_price = min(amounts)
        old_price = max(amounts) if len(amounts) > 1 else None
        if old_price and old_price > current_price:
            return old_price, current_price
        return current_price, None

    @staticmethod
    def _extract_numbers(text: str) -> List[float]:
        values: List[float] = []
        for match in re.findall(r"\d+(?:[.,]\d+)?", text):
            try:
                values.append(float(match.replace(",", ".")))
            except ValueError:
                continue
        return values


class AkbalMarketAdapter(MagentoAutocompleteAdapter):
    market_key = "akbal_market_zonguldak"
    base_url = "https://www.akbalmarket.com"

    def __init__(self) -> None:
        super().__init__(max_products=25, request_timeout=8, max_retries=0)
        self.seed_queries = ("domates",)
