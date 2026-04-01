import json
import re
from typing import List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base import FetchContext, MarketAdapter, RawOffer


class MismarAdapter(MarketAdapter):
    market_key = "mismar_konya"

    def __init__(self, max_links: int = 5000):
        self.max_links = max_links
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
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
        response = self.session.get("https://www.mismarsanalmarket.com/sitemap.xml", timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml")
        links = [loc.text.strip() for loc in soup.find_all("loc") if "mismarsanalmarket.com" in loc.text]
        product_links = [link for link in links if len(urlparse(link).path.strip("/").split("/")) > 1]
        return product_links[: self.max_links]

    def _fetch_product(self, url: str) -> Optional[RawOffer]:
        response = self.session.get(url, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.content, "html.parser")
        name_tag = soup.select_one("h1.product-title, .product-name, h1")
        price_tag = soup.select_one(".current-price, .price, .product-price, .last-price")

        if name_tag is None or price_tag is None:
            return None

        name = name_tag.get_text(strip=True)
        price = self._parse_price(price_tag.get_text(" ", strip=True))
        if price is None or price <= 0:
            return None

        image_url = self._extract_image(soup)
        breadcrumb = soup.select(".breadcrumb li, .breadcrumb-item")
        category = breadcrumb[-2].get_text(strip=True) if len(breadcrumb) > 1 else "Genel"

        return RawOffer(
            source_product_id=self._product_id_from_url(url),
            source_category=category,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=price,
            promo_price=None,
            stock_status="unknown",
            image_url=image_url,
            payload_json=None,
        )

    @staticmethod
    def _product_id_from_url(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        return path.split("/")[-1]

    @staticmethod
    def _parse_price(value: str) -> Optional[float]:
        cleaned = re.sub(r"[^\d,.\s]", "", value).strip().replace(",", ".")
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        return float(match.group(0)) if match else None

    @staticmethod
    def _extract_image(soup: BeautifulSoup) -> Optional[str]:
        meta_image = soup.find("meta", property="og:image")
        if meta_image and meta_image.get("content"):
            return meta_image["content"]

        for selector in [".product-image img", ".main-image img", 'img[itemprop="image"]']:
            image_tag = soup.select_one(selector)
            if image_tag:
                source = image_tag.get("data-original") or image_tag.get("data-src") or image_tag.get("src")
                if source:
                    return source if source.startswith("http") else f"https://www.mismarsanalmarket.com{source}"

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except Exception:
                continue
            if isinstance(data, list) and data:
                data = data[0]
            if isinstance(data, dict) and "image" in data:
                image = data["image"]
                if isinstance(image, list):
                    image = image[0]
                if isinstance(image, str):
                    return image
        return None
