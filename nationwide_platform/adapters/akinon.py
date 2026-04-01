import gzip
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .base import RawOffer
from .custom_html import SitemapProductDetailAdapter


class AkinonGzipSitemapProductAdapter(SitemapProductDetailAdapter):
    market_key = "akinon_product_sitemap"
    base_url = ""
    sitemap_path = ""
    default_brand: Optional[str] = None
    excluded_prefixes = (
        "/users",
        "/baskets",
        "/orders",
        "/search",
        "/blog",
        "/stores",
        "/sayfalar",
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

    def _product_links(self):
        sitemap_url = urljoin(self.base_url, self.sitemap_path)
        response = self._safe_get(sitemap_url)
        if response is None or response.status_code != 200:
            return []
        payload = response.content or b""
        if payload[:2] == b"\x1f\x8b":
            sitemap_text = gzip.decompress(payload).decode("utf-8", "ignore")
        else:
            sitemap_text = response.text or payload.decode("utf-8", "ignore")
        product_links = []
        seen_urls = set()
        for url in re.findall(r"<loc>(.*?)</loc>", sitemap_text):
            url = url.strip()
            if not self._is_product_url(url) or url in seen_urls:
                continue
            seen_urls.add(url)
            product_links.append(url)
            if len(product_links) >= self.max_products:
                break
        return product_links

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
        breadcrumb_names = [
            self._clean_text(element.get_text(" ", strip=True))
            for element in soup.select(".breadcrumb__link")
        ]
        filtered = [
            name for name in breadcrumb_names
            if name and name not in {"Anasayfa", "Home", product_name}
        ]
        if filtered:
            return filtered[-1]

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
                if not isinstance(candidate, dict) or candidate.get("@type") != "BreadcrumbList":
                    continue
                items = candidate.get("itemListElement") or []
                names = [item.get("name", "").strip() for item in items if isinstance(item, dict)]
                filtered = [name for name in names if name and name not in {"Anasayfa", "Home", product_name}]
                if filtered:
                    return filtered[-1]
        return "Genel"

    def _extract_stock_status(self, soup: BeautifulSoup) -> str:
        schema = self._extract_product_schema(soup)
        offers = schema.get("offers")
        offer_rows = offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []
        for offer in offer_rows:
            if not isinstance(offer, dict):
                continue
            availability = str(offer.get("availability") or "").lower()
            if "instock" in availability:
                return "in_stock"
            if "outofstock" in availability:
                return "out_of_stock"

        page_text = soup.get_text(" ", strip=True).lower()
        if "stokta yok" in page_text or "out of stock" in page_text:
            return "out_of_stock"
        if soup.select_one(".js-add-to-cart-button") or soup.select_one(".js-add-to-cart"):
            return "in_stock"
        return "unknown"

    def _extract_prices(self, soup: BeautifulSoup, schema: dict):
        current_price, old_price = super()._extract_prices(soup, schema)
        if current_price is not None:
            return current_price, old_price

        meta_price = soup.select_one("meta[property='og:price:amount'][content]")
        if meta_price is not None:
            current_price = self._parse_price(meta_price.get("content"))
            if current_price is not None:
                return current_price, None

        price_tag = soup.select_one("pz-price")
        if price_tag is not None:
            current_price = self._parse_price(price_tag.get_text(" ", strip=True))
            if current_price is not None:
                return current_price, None
        return None, None

    def _extract_image(self, soup: BeautifulSoup, schema: dict) -> Optional[str]:
        og_image = soup.select_one("meta[property='og:image'][content]")
        if og_image is not None:
            return self._clean_text(og_image.get("content"))
        return super()._extract_image(soup, schema)

    def _parse_product_page(self, url: str, html_text: str) -> Optional[RawOffer]:
        offer = super()._parse_product_page(url, html_text)
        if offer is None:
            return None

        soup = BeautifulSoup(html_text, "html.parser")
        data_sku = None
        sku_holder = soup.select_one("[data-sku]")
        if sku_holder is not None:
            data_sku = self._clean_text(sku_holder.get("data-sku"))

        url_barcode = None
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        match = re.search(r"(\d{8,14})$", slug)
        if match:
            url_barcode = match.group(1)

        barcode = offer.source_barcode or data_sku or url_barcode
        if barcode and not re.fullmatch(r"\d{8,14}", barcode):
            barcode = None

        brand = offer.source_brand or self.default_brand
        return replace(offer, source_barcode=barcode, source_brand=brand)

    def _fetch_and_parse(self, url: str) -> Optional[RawOffer]:
        html_text = self._fetch_text(url)
        if not html_text:
            return None
        return self._parse_product_page(url, html_text)


class FlormarAdapter(AkinonGzipSitemapProductAdapter):
    market_key = "flormar_online"
    base_url = "https://www.flormar.com.tr"
    sitemap_path = "/sitemaps/sitemap-products-1.xml.gz"
    default_brand = "Flormar"

    def __init__(self):
        super().__init__(max_products=3000, request_timeout=12, max_retries=0)
