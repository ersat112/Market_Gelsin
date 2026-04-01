import json
import re
import subprocess
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from .base import FetchContext, MarketAdapter, RawOffer


class SokAdapter(MarketAdapter):
    market_key = "cepte_sok"
    base_url = "https://www.sokmarket.com.tr"
    sitemap_index_url = "https://www.sokmarket.com.tr/sitemap/sitemap.xml"

    def __init__(
        self,
        max_links: int = 150,
        max_category_pages: int = 10,
        request_timeout: int = 20,
        max_retries: int = 1,
    ):
        self.max_links = max_links
        self.max_category_pages = max_category_pages
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Referer": f"{self.base_url}/",
            }
        )

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids: Set[str] = set()

        self._collect_listing_page_offers(self.base_url, "Anasayfa", "homepage", offers, seen_ids)
        if len(offers) >= self.max_links:
            return offers[: self.max_links]

        for url in self._group_links():
            self._collect_listing_page_offers(url, None, "campaign_group", offers, seen_ids)
            if len(offers) >= self.max_links:
                return offers[: self.max_links]

        for url in self._category_links():
            self._collect_listing_page_offers(url, None, "category_sitemap", offers, seen_ids)
            if len(offers) >= self.max_links:
                return offers[: self.max_links]
        return offers[: self.max_links]

    def _collect_listing_page_offers(
        self,
        url: str,
        default_category: Optional[str],
        surface: str,
        offers: List[RawOffer],
        seen_ids: Set[str],
    ) -> None:
        html = self._fetch_text(url)
        if not html:
            return
        soup = BeautifulSoup(html, "html.parser")
        category = self._listing_category_name(soup, url, default_category)
        for link in soup.select("a[href*='-p-']"):
            offer = self._parse_listing_card(link, category, surface)
            if offer is None or offer.source_product_id in seen_ids:
                continue
            seen_ids.add(offer.source_product_id)
            offers.append(offer)
            if len(offers) >= self.max_links:
                return

    def _group_links(self) -> List[str]:
        html = self._fetch_text(self.base_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        seen: Set[str] = set()
        for anchor in soup.select("a[href*='-sgrp-'], a[href*='-pgrp-']"):
            href = anchor.get("href") or ""
            absolute_url = urljoin(self.base_url, href)
            if absolute_url in seen:
                continue
            seen.add(absolute_url)
            links.append(absolute_url)
        return links

    def _category_links(self) -> List[str]:
        sitemap_xml = self._market_sitemap_xml("market-category")
        if not sitemap_xml:
            return []
        soup = BeautifulSoup(sitemap_xml, "xml")
        links: List[str] = []
        seen: Set[str] = set()
        for loc in soup.find_all("loc"):
            url = loc.get_text(strip=True)
            if self.base_url not in url or url in seen:
                continue
            seen.add(url)
            links.append(url)
            if len(links) >= self.max_category_pages:
                break
        return links

    def _product_links(self) -> List[str]:
        sitemap_xml = self._market_sitemap_xml("market-product")
        if not sitemap_xml:
            return []
        soup = BeautifulSoup(sitemap_xml, "xml")
        links = [loc.text.strip() for loc in soup.find_all("loc") if self.base_url in loc.text]
        return links[: self.max_links]

    def _market_sitemap_xml(self, keyword: str) -> Optional[str]:
        sitemap_index = self._fetch_text(self.sitemap_index_url)
        if not sitemap_index:
            return None
        index_soup = BeautifulSoup(sitemap_index, "xml")
        for loc in index_soup.find_all("loc"):
            link = loc.get_text(strip=True)
            if keyword in link:
                return self._fetch_text(link)
        return None

    def _fetch_product(self, url: str) -> Optional[RawOffer]:
        html = self._fetch_text(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        product = {}
        if next_data_tag is not None and next_data_tag.string:
            try:
                data = json.loads(next_data_tag.string)
                product = data.get("props", {}).get("pageProps", {}).get("product", {}) or {}
            except json.JSONDecodeError:
                product = {}

        name = product.get("name") or self._extract_product_name(soup)
        if not name:
            return None

        price = product.get("price", {}).get("salesPrice")
        if price is None:
            price = product.get("salesPrice")
        if price in {None, "", 0}:
            price = self._extract_current_price(soup)
        if price in {None, "", 0}:
            return None

        images = product.get("images") or []
        image_url = images[0].get("url") if images and isinstance(images[0], dict) else None
        if not image_url:
            image_url = self._extract_image_url(soup)
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(self.base_url, image_url)

        category = product.get("category", {}).get("name") if isinstance(product.get("category"), dict) else None
        if not category:
            category = self._extract_category_name(soup)

        old_price = self._extract_old_price(soup)
        listed_price = float(old_price) if old_price and old_price > float(price) else float(price)
        promo_price = float(price) if listed_price > float(price) else None

        return RawOffer(
            source_product_id=self._product_id_from_url(url),
            source_category=category or "Genel",
            source_name=name,
            source_brand=product.get("brand", {}).get("name") if isinstance(product.get("brand"), dict) else None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(product, ensure_ascii=True),
        )

    def _parse_listing_card(self, link: Tag, category: str, surface: str) -> Optional[RawOffer]:
        href = (link.get("href") or "").strip()
        if "-p-" not in href:
            return None

        title_tag = link.select_one("[class*='CProductCard-module_title__']")
        if title_tag is None:
            return None

        name = self._clean_text(title_tag.get_text(" ", strip=True))
        if not name:
            return None

        current_price = self._extract_current_price(link)
        if current_price is None or current_price <= 0:
            return None

        old_price = self._extract_old_price(link)
        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if listed_price > current_price else None

        image_tag = link.select_one("img[src]")
        image_url = None
        if image_tag is not None:
            image_url = urljoin(self.base_url, image_tag.get("src"))

        payload = {
            "url": urljoin(self.base_url, href),
            "surface": surface,
            "category": category,
        }

        return RawOffer(
            source_product_id=self._product_id_from_url(href),
            source_category=category,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    def _fetch_text(self, url: str) -> Optional[str]:
        response = self._safe_get(url)
        if response is not None and response.status_code == 200 and response.text:
            return response.text
        return self._curl_get_text(url)

    def _safe_get(self, url: str) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                return self.session.get(url, timeout=self.request_timeout)
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _curl_get_text(self, url: str) -> Optional[str]:
        command = [
            "curl",
            "-L",
            "--silent",
            "--show-error",
            "--max-time",
            str(self.request_timeout),
            "--header",
            f"User-Agent: {self.session.headers['User-Agent']}",
            "--header",
            f"Referer: {self.session.headers['Referer']}",
            "--url",
            url,
        ]
        for _ in range(self.max_retries + 1):
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode == 0 and completed.stdout.strip():
                return completed.stdout
        return None

    @staticmethod
    def _clean_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @staticmethod
    def _price_from_text(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        matches = re.findall(r"\d+(?:[.,]\d+)?", value)
        if not matches:
            return None
        try:
            return float(matches[-1].replace(",", "."))
        except ValueError:
            return None

    def _extract_current_price(self, root: Tag) -> Optional[float]:
        discounted = root.select_one("[class*='CPriceBox-module_discountedPrice__']")
        if discounted is not None:
            return self._price_from_text(discounted.get_text(" ", strip=True))
        current = root.select_one("[class*='CPriceBox-module_price__']")
        if current is not None:
            return self._price_from_text(current.get_text(" ", strip=True))
        return None

    def _extract_old_price(self, root: Tag) -> Optional[float]:
        discounted = root.select_one("[class*='CPriceBox-module_discountedPrice__']")
        if discounted is None:
            return None
        price_nodes = root.select("[class*='CPriceBox-module_price__']")
        if not price_nodes:
            return None
        return self._price_from_text(price_nodes[0].get_text(" ", strip=True))

    def _listing_category_name(
        self,
        soup: BeautifulSoup,
        page_url: str,
        fallback: Optional[str],
    ) -> str:
        heading = soup.find("h1") or soup.find("h2")
        if heading is not None:
            name = self._clean_text(heading.get_text(" ", strip=True))
            if name:
                return name

        breadcrumb_links = soup.select("nav a[href]")
        if breadcrumb_links:
            name = self._clean_text(breadcrumb_links[-1].get_text(" ", strip=True))
            if name:
                return name

        title = soup.find("title")
        if title is not None:
            text = self._clean_text(title.get_text(" ", strip=True))
            if text:
                return text.replace(" - Cepte Şok", "").replace(" Çeşitleri ve Fiyatları", "").strip()

        if fallback:
            return fallback

        slug = urlparse(page_url).path.rstrip("/").split("/")[-1]
        slug = slug.split("-c-")[0].split("-sgrp-")[0].split("-pgrp-")[0]
        return slug.replace("-", " ").title() if slug else "Genel"

    def _extract_product_name(self, soup: BeautifulSoup) -> Optional[str]:
        heading = soup.find("h1")
        if heading is not None:
            name = self._clean_text(heading.get_text(" ", strip=True))
            if name:
                return name
        title = soup.find("title")
        if title is not None:
            text = self._clean_text(title.get_text(" ", strip=True))
            if text:
                return text.replace(" - Cepte Şok", "").strip()
        return None

    def _extract_image_url(self, soup: BeautifulSoup) -> Optional[str]:
        image_tag = soup.select_one("img[alt='product-thumb'][src]") or soup.select_one("link[rel='preload'][as='image'][href]")
        if image_tag is None:
            return None
        return image_tag.get("src") or image_tag.get("href")

    def _extract_category_name(self, soup: BeautifulSoup) -> Optional[str]:
        breadcrumb_links = soup.select("nav a[href]")
        if breadcrumb_links:
            name = self._clean_text(breadcrumb_links[-1].get_text(" ", strip=True))
            if name:
                return name
        return "Genel"

    @staticmethod
    def _product_id_from_url(url: str) -> str:
        path = urlparse(url).path
        return path.rstrip("/").split("-p-")[-1] if "-p-" in path else path.rstrip("/").split("/")[-1]
