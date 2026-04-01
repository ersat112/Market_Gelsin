import json
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .base import FetchContext, RawOffer
from .custom_html import HtmlStorefrontAdapter


class BizimToptanAdapter(HtmlStorefrontAdapter):
    market_key = "bizim_toptan_online"
    base_url = "https://www.bizimtoptan.com.tr"
    root_category_slugs: Tuple[str, ...] = (
        "temel-gida",
        "sivi-yag-margarin",
        "atistirmalik",
        "icecek",
        "sarkuteri-kahvaltilik",
        "et-urunleri-ve-sarkuteri",
        "unlu-mamuller",
        "bebek-urunleri",
        "evcil-hayvan",
        "temizlik",
        "kisisel-bakim",
        "gida-disi",
        "horeca-urunleri",
        "bakkallara-ozel",
        "kazandiran-urunler",
    )

    def __init__(
        self,
        max_products: int = 5000,
        max_pages_per_category: int = 50,
        request_timeout: int = 20,
        max_retries: int = 1,
    ):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products
        self.max_pages_per_category = max_pages_per_category

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids: Set[str] = set()
        for category_path in self._discover_root_category_paths():
            max_page = 1
            for page_number in range(1, self.max_pages_per_category + 1):
                if page_number > max_page:
                    break
                response = self._safe_get(self._page_url(category_path, page_number))
                if response is None:
                    break
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.select(".product-box-container")
                if not cards:
                    break
                if page_number == 1:
                    max_page = min(self.max_pages_per_category, self._max_page_number(soup))
                category_name = self._category_name(soup, category_path)
                for card in cards:
                    offer = self._parse_card(card, category_name)
                    if offer is None or offer.source_product_id in seen_ids:
                        continue
                    seen_ids.add(offer.source_product_id)
                    offers.append(offer)
                    if len(offers) >= self.max_products:
                        return offers
        return offers

    def _discover_root_category_paths(self) -> List[str]:
        response = self._safe_get(self.base_url)
        if response is None:
            return [f"/{slug}" for slug in self.root_category_slugs]
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        discovered: List[str] = []
        seen_paths: Set[str] = set()
        for anchor in soup.select("a[href]"):
            category_path = self._normalize_root_category_path(anchor.get("href"))
            if category_path is None or category_path in seen_paths:
                continue
            seen_paths.add(category_path)
            discovered.append(category_path)
        if discovered:
            return discovered
        return [f"/{slug}" for slug in self.root_category_slugs]

    def _normalize_root_category_path(self, href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        path = urlparse(urljoin(self.base_url, href)).path.rstrip("/")
        if not path:
            return None
        first_segment = path.strip("/").split("/", 1)[0]
        if first_segment not in self.root_category_slugs:
            return None
        return f"/{first_segment}"

    def _page_url(self, category_path: str, page_number: int) -> str:
        if page_number <= 1:
            return urljoin(self.base_url, category_path)
        return f"{urljoin(self.base_url, category_path)}?pagenumber={page_number}&paginationType=10"

    @staticmethod
    def _max_page_number(soup: BeautifulSoup) -> int:
        max_page = 1
        for anchor in soup.select("a[href*='pagenumber=']"):
            href = anchor.get("href") or ""
            query = parse_qs(urlparse(href).query)
            page_values = query.get("pagenumber") or []
            if not page_values:
                continue
            try:
                max_page = max(max_page, int(page_values[0]))
            except ValueError:
                continue
        return max_page

    def _category_name(self, soup: BeautifulSoup, category_path: str) -> str:
        heading = soup.select_one("h1")
        if heading is not None:
            heading_text = self._clean_text(heading.get_text(" ", strip=True))
            if heading_text:
                return heading_text
        title_tag = soup.select_one("title")
        if title_tag is not None:
            title_text = self._clean_text(title_tag.get_text(" ", strip=True))
            if title_text:
                return title_text.split(" | ", 1)[0]
        return category_path.strip("/").replace("-", " ").title()

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        source_product_id = self._clean_text(card.get("data-productid")) or None
        detail_anchor = card.select_one("a.product-item[href]") or card.select_one("a.productbox-link[href]")
        name_tag = card.select_one(".productbox-name")
        price_tag = card.select_one(".product-price")
        if source_product_id is None or detail_anchor is None or name_tag is None or price_tag is None:
            return None

        name = self._clean_text(name_tag.get_text(" ", strip=True))
        current_price = self._parse_price(price_tag.get_text(" ", strip=True))
        if name is None or current_price is None or current_price <= 0:
            return None

        image_tag = card.select_one("img[data-src]") or card.select_one("img[src]")
        image_url = None
        if image_tag is not None:
            image_path = image_tag.get("data-src") or image_tag.get("src")
            if image_path:
                image_url = urljoin(self.base_url, image_path)

        analytics_payload = self._parse_analytics_payload(detail_anchor.get("data-enhanced-productclick"))
        brand = self._clean_text(analytics_payload.get("item_brand")) if analytics_payload else None
        listed_price, old_price = self._parse_price_values(card.get_text(" ", strip=True))
        if listed_price is None:
            listed_price = current_price
        promo_price = current_price if old_price and old_price > current_price else None
        if old_price and old_price > listed_price:
            listed_price = old_price

        payload = {
            "url": urljoin(self.base_url, detail_anchor.get("href") or ""),
            "category": category_name,
            "stock_quantity": card.get("data-stock"),
            "quantity_unit": card.get("data-quantityunit"),
        }
        if analytics_payload:
            payload["analytics"] = analytics_payload

        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=brand,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=self._stock_status(card.get("data-stock")),
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _parse_analytics_payload(raw_value: Optional[str]) -> Optional[Dict[str, object]]:
        if not raw_value:
            return None
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            return payload
        return None

    @staticmethod
    def _coerce_float(value: object) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            matches = re.findall(r"\d+(?:[.,]\d+)?", value)
            if not matches:
                return None
            try:
                return float(matches[-1].replace(",", "."))
            except ValueError:
                return None
        return None

    @staticmethod
    def _stock_status(value: object) -> str:
        quantity = BizimToptanAdapter._coerce_float(value)
        if quantity is None:
            return "unknown"
        if quantity > 0:
            return "in_stock"
        return "out_of_stock"


class TarimKrediKoopAdapter(HtmlStorefrontAdapter):
    market_key = "tarim_kredi_koop_market"
    base_url = "https://www.tkkoop.com.tr"
    fallback_root_categories: Tuple[str, ...] = (
        "/urun-kategori/temel-gida-urunleri",
        "/urun-kategori/sivi-yag-ve-margarinler",
        "/urun-kategori/sarkuteri-kahvaltilik",
        "/urun-kategori/icecekler",
        "/urun-kategori/atistirmalik",
        "/urun-kategori/dondurulmus-urunler",
        "/urun-kategori/et-et-urunleri",
        "/urun-kategori/sut",
        "/urun-kategori/meyve-sebze",
        "/urun-kategori/kagit-urunleri",
        "/urun-kategori/kisisel-bakim",
        "/urun-kategori/temizlik-urunleri",
        "/urun-kategori/ev-yasam",
        "/urun-kategori/saglik-urunleri",
    )

    def __init__(
        self,
        max_products: int = 5000,
        max_pages_per_category: int = 60,
        request_timeout: int = 20,
        max_retries: int = 1,
    ):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products
        self.max_pages_per_category = max_pages_per_category

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids: Set[str] = set()
        for category_path in self._discover_root_category_paths():
            max_page = 1
            for page_number in range(1, self.max_pages_per_category + 1):
                if page_number > max_page:
                    break
                response = self._safe_get(self._page_url(category_path, page_number))
                if response is None:
                    break
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.select(".product-card")
                if not cards:
                    break
                if page_number == 1:
                    max_page = min(self.max_pages_per_category, self._max_page_number(soup))
                category_name = self._category_name(soup, category_path)
                for card in cards:
                    offer = self._parse_card(card, category_name)
                    if offer is None or offer.source_product_id in seen_ids:
                        continue
                    seen_ids.add(offer.source_product_id)
                    offers.append(offer)
                    if len(offers) >= self.max_products:
                        return offers
        return offers

    def _discover_root_category_paths(self) -> List[str]:
        response = self._safe_get(self.base_url)
        if response is None:
            return list(self.fallback_root_categories)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        discovered: List[str] = []
        seen_paths: Set[str] = set()
        for anchor in soup.select("a[href*='/urun-kategori/']"):
            path = self._normalize_root_category_path(anchor.get("href"))
            if path is None or path in seen_paths:
                continue
            seen_paths.add(path)
            discovered.append(path)
        if discovered:
            return discovered
        return list(self.fallback_root_categories)

    def _normalize_root_category_path(self, href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        path = urlparse(urljoin(self.base_url, href)).path.rstrip("/")
        segments = path.strip("/").split("/")
        if len(segments) != 2 or segments[0] != "urun-kategori":
            return None
        return f"/{segments[0]}/{segments[1]}"

    def _page_url(self, category_path: str, page_number: int) -> str:
        if page_number <= 1:
            return urljoin(self.base_url, category_path)
        return f"{urljoin(self.base_url, category_path)}?page={page_number}"

    @staticmethod
    def _max_page_number(soup: BeautifulSoup) -> int:
        max_page = 1
        for anchor in soup.select("a[href*='?page=']"):
            href = anchor.get("href") or ""
            query = parse_qs(urlparse(href).query)
            page_values = query.get("page") or []
            if not page_values:
                continue
            try:
                max_page = max(max_page, int(page_values[0]))
            except ValueError:
                continue
        return max_page

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        product_link = card.select_one("a[href*='/urun/']")
        title_tag = card.select_one(".product-title")
        price_container = card.select_one(".ss_urun5")
        if product_link is None or title_tag is None or price_container is None:
            return None

        href = product_link.get("href") or ""
        source_product_id = self._product_id_from_href(href)
        name = self._clean_text(title_tag.get_text(" ", strip=True))
        current_price = self._extract_price(price_container)
        if source_product_id is None or name is None or current_price is None or current_price <= 0:
            return None

        image_tag = card.select_one(".product-image img")
        image_url = None
        if image_tag is not None:
            image_path = image_tag.get("src") or image_tag.get("data-src")
            if image_path:
                image_url = urljoin(self.base_url, image_path)

        payload = {
            "url": urljoin(self.base_url, href),
            "category": category_name,
        }
        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=self._brand_from_name(name),
            source_size=None,
            listed_price=current_price,
            promo_price=None,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _product_id_from_href(href: str) -> Optional[str]:
        path = urlparse(href).path
        if "/urun/" not in path:
            return None
        slug = path.strip("/").split("/")[-1]
        return slug or None

    @staticmethod
    def _brand_from_name(name: str) -> Optional[str]:
        first_token = name.split()[0].strip()
        if len(first_token) <= 1:
            return None
        return first_token.title()

    @staticmethod
    def _extract_price(price_container: Tag) -> Optional[float]:
        price_html = str(price_container)
        whole_decimal_match = re.search(r">([\d.]+)\s*,\s*<span>\s*(\d{2})\s*</span>", price_html, re.S)
        if whole_decimal_match:
            whole = whole_decimal_match.group(1).replace(".", "")
            decimal = whole_decimal_match.group(2)
            try:
                return float(f"{whole}.{decimal}")
            except ValueError:
                return None
        return HtmlStorefrontAdapter._parse_price(price_container.get_text(" ", strip=True))

    def _category_name(self, soup: BeautifulSoup, category_path: str) -> str:
        heading = soup.select_one("h1")
        if heading is not None:
            heading_text = self._clean_text(heading.get_text(" ", strip=True))
            if heading_text:
                return heading_text
        title_tag = soup.select_one("title")
        if title_tag is not None:
            title_text = self._clean_text(title_tag.get_text(" ", strip=True))
            if title_text:
                return title_text.split(" - ", 1)[0]
        slug = category_path.strip("/").split("/")[-1]
        return slug.replace("-", " ").title()
