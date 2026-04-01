import html
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .base import RawOffer
from .custom_html import SitemapProductDetailAdapter


class MyikasProductSitemapAdapter(SitemapProductDetailAdapter):
    market_key = "myikas_product_sitemap"
    base_url = ""
    sitemap_path = ""
    excluded_prefixes = (
        "/giris",
        "/hesabim",
        "/sepet",
        "/search",
        "/arama",
        "/collections",
        "/tum-urunler",
        "/blog",
        "/pages",
    )

    def fetch_offers(self, context):
        offers = []
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
        slug = path.lstrip("/")
        if not slug or "/" in slug:
            return False
        return not slug.endswith((".xml", ".gz"))

    def _extract_category(self, soup: BeautifulSoup, product_name: str) -> str:
        for script in soup.select("script[type='application/ld+json']"):
            raw_text = script.string or script.get_text(" ", strip=True)
            if not raw_text:
                continue
            try:
                parsed = json.loads(html.unescape(raw_text))
            except Exception:
                continue
            candidates = parsed if isinstance(parsed, list) else [parsed]
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("@type") != "BreadcrumbList":
                    continue
                category = self._category_from_breadcrumb(candidate, product_name)
                if category:
                    return category
        return "Genel"

    def _extract_stock_status(self, soup: BeautifulSoup) -> str:
        schema = self._extract_product_schema(soup)
        offers = schema.get("offers")
        offer_rows: List[dict] = offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []
        for offer in offer_rows:
            if not isinstance(offer, dict):
                continue
            availability = str(offer.get("availability") or "").lower()
            if "instock" in availability:
                return "in_stock"
            if "outofstock" in availability:
                return "out_of_stock"
        return "unknown"

    def _fetch_and_parse(self, url: str) -> Optional[RawOffer]:
        html_text = self._fetch_text(url)
        if not html_text:
            return None
        return self._parse_product_page(url, html_text)

    @staticmethod
    def _category_from_breadcrumb(schema: dict, product_name: str) -> Optional[str]:
        items = schema.get("itemListElement") or []
        names: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str):
                cleaned = name.strip()
                if cleaned:
                    names.append(cleaned)
        filtered = [
            name for name in names
            if name not in {"T-Shop | Güzellik Bakım Marketi", "Tüm Ürünler", product_name}
        ]
        return filtered[-1] if filtered else None


class TShopAdapter(MyikasProductSitemapAdapter):
    market_key = "tshop_online"
    base_url = "https://tshop.com.tr"
    sitemap_path = "https://tshop.com.tr/products.xml"

    def __init__(self):
        super().__init__(max_products=4000, request_timeout=12, max_retries=0)
