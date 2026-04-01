import json
import re
from typing import List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base import FetchContext, MarketAdapter, RawOffer
from .http_fallback import curl_get


class TicimaxSitemapAdapter(MarketAdapter):
    market_key = "ticimax"
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
            if "/sitemap/products/" in loc.text
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
                if self.base_url.replace("https://", "") in loc.text
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
        model = self._extract_product_detail_model(html)

        name_tag = soup.select_one("h1")
        name = model.get("productName") or (name_tag.get_text(strip=True) if name_tag else None)
        if not name:
            return None

        price = self._extract_price(soup)
        if price is None or price <= 0:
            return None

        breadcrumb = [
            element.get_text(strip=True)
            for element in soup.select(".breadcrumb a")
            if element.get_text(strip=True) not in {"Anasayfa", "Kategoriler"}
        ]
        category = breadcrumb[-1] if breadcrumb else "Genel"

        image_url = self._extract_image(soup)
        brand = self._clean_optional_text(model.get("brandName"))

        return RawOffer(
            source_product_id=str(model.get("productId") or self._product_id_from_url(url)),
            source_category=category,
            source_name=name,
            source_brand=brand,
            source_size=None,
            listed_price=price,
            promo_price=None,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(model, ensure_ascii=True),
            source_barcode=self._clean_optional_text(model.get("barcode") or model.get("combinationBarcode")),
        )

    @staticmethod
    def _extract_product_detail_model(html: str) -> dict:
        match = re.search(r"var productDetailModel = (\{.*?\});", html, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except Exception:
            return {}

    @staticmethod
    def _extract_price(soup: BeautifulSoup) -> Optional[float]:
        for selector in ["#indirimliFiyat", "#fiyat2", ".PriceList .indirimliFiyat"]:
            tag = soup.select_one(selector)
            if tag:
                price = TicimaxSitemapAdapter._parse_price(tag.get_text(" ", strip=True))
                if price is not None:
                    return price
        return None

    @staticmethod
    def _extract_image(soup: BeautifulSoup) -> Optional[str]:
        meta_image = soup.find("meta", property="og:image")
        if meta_image and meta_image.get("content"):
            return meta_image["content"]
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

    @staticmethod
    def _clean_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _parse_price(value: str) -> Optional[float]:
        cleaned = re.sub(r"[^\d,.\s]", "", value).strip().replace(",", ".")
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        return float(match.group(0)) if match else None


class AsyaMarketAdapter(TicimaxSitemapAdapter):
    market_key = "asya_market_trabzon"
    base_url = "https://www.asyasanalmarket.com"


class Onur360Adapter(TicimaxSitemapAdapter):
    base_url = "https://onur360.com"


class OnurMarketKirklareliAdapter(Onur360Adapter):
    market_key = "onur_market_kirklareli"


class OnurMarketTekirdagAdapter(Onur360Adapter):
    market_key = "onur_market_tekirdag"
