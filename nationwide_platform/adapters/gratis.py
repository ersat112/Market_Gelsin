import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .base import FetchContext, RawOffer
from .custom_html import SitemapProductDetailAdapter


class GratisAdapter(SitemapProductDetailAdapter):
    market_key = "gratis_online"
    base_url = "https://www.gratis.com"
    sitemap_path = "/sitemap/Product-tr-TRY.xml"
    excluded_prefixes = (
        "/sitemap",
        "/markalar",
        "/kampanyalar",
        "/yardim",
        "/hesabim",
        "/sepet",
    )

    def __init__(self):
        super().__init__(max_products=3000, request_timeout=12, max_retries=0)

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        product_links = self._product_links()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._fetch_and_parse, url) for url in product_links]
            for future in as_completed(futures):
                offer = future.result()
                if offer is None:
                    continue
                offers.append(offer)
                if len(offers) >= self.max_products:
                    break
        return offers

    def _is_product_url(self, url: str) -> bool:
        if not url.startswith(self.base_url):
            return False
        path = urlparse(url).path.rstrip("/")
        if not path:
            return False
        if any(path.startswith(prefix) for prefix in self.excluded_prefixes):
            return False
        return bool(re.search(r"-p-\d+$", path))

    def _fetch_and_parse(self, url: str) -> Optional[RawOffer]:
        html_text = self._fetch_text(url)
        if not html_text:
            return None
        return self._parse_product_page(url, html_text)

    def _parse_product_page(self, url: str, html_text: str) -> Optional[RawOffer]:
        product_block = self._extract_product_block(html_text)
        if not product_block:
            return None

        source_product_id = self._extract_value(product_block, r'\\"id\\":\\"([^"]+)\\"')
        stock_status = self._map_stock_status(self._extract_value(product_block, r'\\"stockStatus\\":\\"([^"]+)\\"'))
        discounted_cents = self._extract_int(product_block, r'\\"discountedPrice\\":(\d+)')
        normal_cents = self._extract_int(product_block, r'\\"normalPrice\\":(\d+)')
        if discounted_cents is None and normal_cents is None:
            return None

        current_price = (discounted_cents or normal_cents) / 100.0
        listed_price = (normal_cents / 100.0) if normal_cents else current_price
        promo_price = current_price if normal_cents and discounted_cents and normal_cents > discounted_cents else None

        name = self._extract_attribute_value(product_block, "displayName")
        if not name:
            name = self._extract_page_title(html_text)
        if not name:
            return None

        brand = self._extract_attribute_value(product_block, "brand")
        barcode = self._extract_attribute_value(product_block, "eanUpc")
        if barcode and not re.fullmatch(r"\d{8,14}", barcode):
            barcode = None

        category = self._extract_last_category(product_block) or "Genel"
        image_url = self._extract_value(product_block, r'\\"fileUrl\\":\\"(https://[^"]+)\\"')

        payload = {
            "url": url,
            "stock_status": stock_status,
            "normal_price_cents": normal_cents,
            "discounted_price_cents": discounted_cents,
        }

        return RawOffer(
            source_product_id=source_product_id or self._product_id_from_url(url),
            source_category=category,
            source_name=name,
            source_brand=brand,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=stock_status,
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
            source_barcode=barcode,
        )

    @staticmethod
    def _extract_product_block(html_text: str) -> Optional[str]:
        marker = '\\"productData\\":{'
        start = html_text.find(marker)
        if start == -1:
            return None
        block_start = html_text.find("{", start)
        if block_start == -1:
            return None

        depth = 0
        for index in range(block_start, len(html_text)):
            char = html_text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return html_text[block_start:index + 1]
        return None

    @staticmethod
    def _extract_value(text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text, re.S)
        if not match:
            return None
        return GratisAdapter._decode(match.group(1).strip())

    @staticmethod
    def _extract_int(text: str, pattern: str) -> Optional[int]:
        match = re.search(pattern, text, re.S)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _extract_attribute_value(text: str, key: str) -> Optional[str]:
        pattern = rf'\\"key\\":\\"{re.escape(key)}\\".*?\\"value\\":\\"(.*?)\\"'
        return GratisAdapter._extract_value(text, pattern)

    @staticmethod
    def _extract_last_category(text: str) -> Optional[str]:
        match = re.search(r'\\"key\\":\\"categories\\".*?\\"value\\":\[(.*?)\]', text, re.S)
        if not match:
            return None
        values = re.findall(r'\\"([^"]+)\\"', match.group(1))
        return GratisAdapter._decode(values[-1]) if values else None

    @staticmethod
    def _extract_page_title(html_text: str) -> Optional[str]:
        soup = BeautifulSoup(html_text, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title is not None else ""
        if title.endswith(" - Gratis"):
            title = title[:-9].strip()
        return title or None

    @staticmethod
    def _product_id_from_url(url: str) -> str:
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        match = re.search(r"p-(\d+)$", slug)
        return match.group(1) if match else slug

    @staticmethod
    def _decode(value: str) -> str:
        try:
            return json.loads(f'"{value}"')
        except Exception:
            return value.replace('\\"', '"').strip()

    @staticmethod
    def _map_stock_status(raw_status: Optional[str]) -> str:
        if not raw_status:
            return "unknown"
        lowered = raw_status.lower()
        if lowered in {"high", "medium", "low", "instock", "available"}:
            return "in_stock"
        if lowered in {"out_of_stock", "outofstock", "none", "unavailable"}:
            return "out_of_stock"
        return "unknown"
