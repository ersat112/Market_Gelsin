import html
import json
import re
import subprocess
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from .base import FetchContext, MarketAdapter, RawOffer


class WordPressRestProductAdapter(MarketAdapter):
    market_key = "wordpress_rest_product"
    base_url = ""

    def __init__(self, per_page: int = 100, max_pages: int = 100, request_timeout: int = 15, max_retries: int = 1):
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
        category_map = self._fetch_category_map()
        for page in range(1, self.max_pages + 1):
            products = self._fetch_products(page)
            if not products:
                break
            for product in products:
                offer = self._hydrate_product(product, category_map)
                if offer is not None:
                    offers.append(offer)
            if len(products) < self.per_page:
                break
        return offers

    def _fetch_products(self, page: int) -> List[dict]:
        response = self._safe_get(
            urljoin(self.base_url, "/wp-json/wp/v2/product"),
            params={"page": page, "per_page": self.per_page},
        )
        if response is None:
            return []
        response.raise_for_status()
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

    def _fetch_category_map(self) -> Dict[int, str]:
        response = self._safe_get(
            urljoin(self.base_url, "/wp-json/wp/v2/product_cat"),
            params={"per_page": 100},
        )
        if response is None:
            return {}
        response.raise_for_status()
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, list):
            return {}
        category_map: Dict[int, str] = {}
        for row in payload:
            if not isinstance(row, dict):
                continue
            category_id = row.get("id")
            name = row.get("name")
            if isinstance(category_id, int) and isinstance(name, str):
                category_map[category_id] = html.unescape(name).strip()
        return category_map

    def _hydrate_product(self, product: dict, category_map: Dict[int, str]) -> Optional[RawOffer]:
        product_url = product.get("link")
        if not isinstance(product_url, str) or not product_url:
            return None
        detail_html = self._fetch_text(product_url)
        if not detail_html:
            return None

        name = self._clean_name(product)
        current_price, old_price, stock_status, image_url = self._parse_detail_page(detail_html, product_url)
        if not name or current_price is None or current_price <= 0:
            return None

        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None
        source_product_id = str(product.get("id") or product.get("slug") or "")
        if not source_product_id:
            return None

        category_name = self._category_name(product, category_map)
        unit_label = self._extract_size(name)
        payload = {
            "url": product_url,
            "product_cat": product.get("product_cat") or [],
            "slug": product.get("slug"),
        }

        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=unit_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=stock_status,
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    def _parse_detail_page(self, html_text: str, product_url: str) -> Tuple[Optional[float], Optional[float], str, Optional[str]]:
        soup = BeautifulSoup(html_text, "html.parser")
        current_price = self._parse_price(
            (soup.select_one("ins .woocommerce-Price-amount") or soup.select_one("p.price .woocommerce-Price-amount") or soup.select_one(".woocommerce-Price-amount"))
            .get_text(" ", strip=True)
            if (soup.select_one("ins .woocommerce-Price-amount") or soup.select_one("p.price .woocommerce-Price-amount") or soup.select_one(".woocommerce-Price-amount"))
            is not None
            else ""
        )
        old_price_tag = soup.select_one("del .woocommerce-Price-amount")
        old_price = self._parse_price(old_price_tag.get_text(" ", strip=True)) if old_price_tag is not None else None

        schema = self._extract_product_schema(soup)
        if current_price is None and schema:
            current_price, old_price = self._schema_prices(schema)

        stock_status = self._stock_status(soup, schema)
        image_url = self._extract_image(soup, schema, product_url)
        return current_price, old_price, stock_status, image_url

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

    def _fetch_text(self, url: str) -> Optional[str]:
        response = self._safe_get(url)
        if response is not None and response.status_code == 200 and response.text:
            response.encoding = "utf-8"
            return response.text
        full_url = url
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
            if completed.returncode == 0 and completed.stdout:
                return completed.stdout
        return None

    @staticmethod
    def _clean_name(product: dict) -> Optional[str]:
        title = product.get("title") or {}
        rendered = title.get("rendered") if isinstance(title, dict) else None
        if not isinstance(rendered, str):
            return None
        normalized = " ".join(html.unescape(rendered).split())
        return normalized or None

    @staticmethod
    def _category_name(product: dict, category_map: Dict[int, str]) -> str:
        product_categories = product.get("product_cat") or []
        if isinstance(product_categories, list):
            for category_id in product_categories:
                if isinstance(category_id, int) and category_id in category_map:
                    return category_map[category_id]
        class_list = product.get("class_list") or {}
        if isinstance(class_list, dict):
            for class_name in class_list.values():
                if isinstance(class_name, str) and class_name.startswith("product_cat-"):
                    return class_name.split("product_cat-", 1)[1].replace("-", " ").title()
        return "Genel"

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        matches = re.findall(r"\d+(?:[.,]\d+)?", text)
        if not matches:
            return None
        try:
            normalized = matches[-1]
            if "," in normalized and "." in normalized:
                if normalized.rfind(",") > normalized.rfind("."):
                    normalized = normalized.replace(".", "").replace(",", ".")
                else:
                    normalized = normalized.replace(",", "")
            else:
                normalized = normalized.replace(",", ".")
            return float(normalized)
        except ValueError:
            return None

    @staticmethod
    def _extract_product_schema(soup: BeautifulSoup) -> dict:
        for script in soup.select("script[type='application/ld+json']"):
            raw_text = script.get_text(" ", strip=True)
            if not raw_text:
                continue
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                continue
            graphs = parsed.get("@graph") if isinstance(parsed, dict) else None
            candidates = graphs if isinstance(graphs, list) else [parsed]
            for candidate in candidates:
                if isinstance(candidate, dict) and candidate.get("@type") == "Product":
                    return candidate
        return {}

    def _schema_prices(self, schema: dict) -> Tuple[Optional[float], Optional[float]]:
        offers = schema.get("offers")
        if isinstance(offers, dict):
            current_price = self._parse_price(str(offers.get("price") or offers.get("lowPrice") or ""))
            old_price = self._parse_price(str(offers.get("highPrice") or ""))
            return current_price, old_price
        return None, None

    def _stock_status(self, soup: BeautifulSoup, schema: dict) -> str:
        stock_tag = soup.select_one(".stock")
        stock_text = stock_tag.get_text(" ", strip=True).lower() if stock_tag is not None else ""
        if "stokta yok" in stock_text or "tükendi" in stock_text or "tukendi" in stock_text:
            return "out_of_stock"
        if "stokta" in stock_text:
            return "in_stock"

        offers = schema.get("offers")
        if isinstance(offers, dict):
            availability = str(offers.get("availability") or "").lower()
            if "outofstock" in availability:
                return "out_of_stock"
            if "instock" in availability:
                return "in_stock"
        return "unknown"

    @staticmethod
    def _extract_image(soup: BeautifulSoup, schema: dict, product_url: str) -> Optional[str]:
        image_tag = soup.select_one(".woocommerce-product-gallery__image img")
        if image_tag is not None:
            image_src = image_tag.get("src") or image_tag.get("data-src")
            if image_src:
                return urljoin(product_url, image_src)
        image_value = schema.get("image")
        if isinstance(image_value, str):
            return image_value
        if isinstance(image_value, list) and image_value:
            first_value = image_value[0]
            if isinstance(first_value, str):
                return first_value
        return None

    @staticmethod
    def _extract_size(name: str) -> Optional[str]:
        match = re.search(r"(\d+(?:[.,]\d+)?\s?(?:kg|gr|g|ml|lt|l))", name.lower())
        if match:
            return match.group(1).replace(",", ".")
        return None


class DelvitaAdapter(WordPressRestProductAdapter):
    market_key = "delvita_canakkale"
    base_url = "https://delvita.com.tr"
