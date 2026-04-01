import json
import re
from typing import List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base import FetchContext, MarketAdapter, RawOffer
from .http_fallback import curl_get


class IdeaSoftSitemapAdapter(MarketAdapter):
    market_key = "ideasoft"
    base_url = ""

    def __init__(self, max_products: int = 5000, request_timeout: int = 15, max_retries: int = 1):
        self.max_products = max_products
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Referer": self.base_url,
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        for url in self._product_links():
            offer = self._fetch_product(url)
            if offer is not None:
                offers.append(offer)
        return offers

    def _product_links(self) -> List[str]:
        response = self._safe_get(f"{self.base_url}/sitemap.xml")
        if response is None:
            return []
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml")
        sitemap_links = [
            loc.text.strip()
            for loc in soup.find_all("loc")
            if "sitemap_product_" in loc.text
        ]

        product_links: List[str] = []
        for sitemap_url in sitemap_links:
            sitemap_response = self._safe_get(sitemap_url)
            if sitemap_response is None:
                continue
            sitemap_response.raise_for_status()
            sitemap_soup = BeautifulSoup(sitemap_response.content, "xml")
            product_links.extend(
                loc.text.strip()
                for loc in sitemap_soup.find_all("loc")
                if "/urun/" in loc.text
            )
            if len(product_links) >= self.max_products:
                break
        return product_links[: self.max_products]

    def _fetch_product(self, url: str) -> Optional[RawOffer]:
        response = self._safe_get(url)
        if response is None:
            return None
        if response.status_code != 200:
            return None

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        name_tag = soup.select_one("h1")
        if name_tag is None:
            return None

        name = name_tag.get_text(strip=True)
        price = self._extract_price(soup, html)
        if price is None or price <= 0:
            return None

        category = self._extract_string_field(html, "categoryName") or "Genel"
        brand = self._extract_string_field(html, "brandName")
        image_url = self._extract_image(soup, html)

        payload = {
            "id": self._extract_string_field(html, "id"),
            "sku": self._extract_string_field(html, "sku"),
            "categoryName": category,
            "brandName": brand,
            "salePrice": price,
            "primaryImageUrl": image_url,
        }

        return RawOffer(
            source_product_id=self._extract_string_field(html, "sku") or self._product_id_from_url(url),
            source_category=category,
            source_name=name,
            source_brand=brand,
            source_size=None,
            listed_price=price,
            promo_price=None,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _extract_string_field(html: str, field_name: str) -> Optional[str]:
        pattern = rf"{re.escape(field_name)}:\s*\"(.*?)\""
        match = re.search(pattern, html)
        if not match:
            return None
        value = match.group(1).strip()
        return value or None

    @staticmethod
    def _extract_price(soup: BeautifulSoup, html: str) -> Optional[float]:
        price_meta = soup.select_one('[itemprop="price"]')
        if price_meta and price_meta.get("content"):
            try:
                return float(price_meta["content"])
            except ValueError:
                pass

        match = re.search(r"salePrice:\s*([0-9.]+)", html)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _extract_image(soup: BeautifulSoup, html: str) -> Optional[str]:
        meta_image = soup.find("meta", property="og:image")
        if meta_image and meta_image.get("content"):
            return meta_image["content"]
        image_path = IdeaSoftSitemapAdapter._extract_string_field(html, "primaryImageUrl")
        if image_path:
            return image_path if image_path.startswith("http") else f"https:{image_path}"
        return None

    def _safe_get(self, url: str) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                return self.session.get(url, timeout=self.request_timeout)
            except requests.RequestException as exc:
                last_error = exc
        fallback = curl_get(
            url=url,
            timeout=self.request_timeout,
            user_agent=self.user_agent,
            referer=self.base_url,
        )
        if fallback is not None:
            return fallback
        if last_error is not None:
            return None
        return None

    @staticmethod
    def _product_id_from_url(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        return path.split("-")[-1]


class CarmarAdapter(IdeaSoftSitemapAdapter):
    market_key = "carmar_diyarbakir"
    base_url = "https://www.carmar.com.tr"
