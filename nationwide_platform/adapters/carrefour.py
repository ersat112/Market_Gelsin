import json
import re
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup, Tag

from .base import FetchContext, MarketAdapter, RawOffer

try:
    import cloudscraper
except ImportError:  # pragma: no cover - fallback only matters outside this env
    cloudscraper = None


class CarrefourAdapter(MarketAdapter):
    market_key = "carrefoursa_online_market"
    base_url = "https://www.carrefoursa.com"

    def __init__(
        self,
        max_products: int = 1500,
        max_categories: int = 90,
        request_timeout: int = 30,
        max_retries: int = 1,
    ) -> None:
        self.max_products = max_products
        self.max_categories = max_categories
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.session = self._build_session()

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()

        for category_code, category_label in self._discover_category_codes():
            page_count = 1
            for page in range(1, 40):
                soup = self._fetch_category_page(category_code=category_code, page=page)
                if soup is None:
                    break

                product_list = soup.select_one("ul.product-listing.product-grid")
                if product_list is None:
                    break

                try:
                    page_count = int(product_list.get("data-maxpagenumber") or "1")
                except ValueError:
                    page_count = 1

                cards = product_list.select("li.product-listing-item")
                if not cards:
                    break

                for card in cards:
                    offer = self._parse_card(card, category_label)
                    if offer is None or offer.source_product_id in seen_ids:
                        continue
                    seen_ids.add(offer.source_product_id)
                    offers.append(offer)
                    if len(offers) >= self.max_products:
                        return offers

                if page >= page_count:
                    break

        return offers

    def _build_session(self):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"{self.base_url}/",
        }
        if cloudscraper is not None:
            session = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
            session.headers.update(headers)
            return session
        session = requests.Session()
        session.headers.update(headers)
        return session

    def _discover_category_codes(self) -> Tuple[Tuple[str, str], ...]:
        prioritized = list(self._fallback_category_codes())
        seen_codes = {code for code, _ in prioritized}
        response = self._safe_get(f"{self.base_url}/")
        if response is None:
            return tuple(prioritized[: self.max_categories])

        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("a[href*='/c/']"):
            href = (anchor.get("href") or "").strip()
            match = re.search(r"/c/(\d+)$", href)
            if not match:
                continue
            code = match.group(1)
            label = self._clean_text(anchor.get_text(" ", strip=True))
            if not label or label in {"Tüm Ürünleri Gör", "Tum Urunleri Gor"} or code in seen_codes:
                continue
            seen_codes.add(code)
            prioritized.append((code, label))
            if len(prioritized) >= self.max_categories:
                break
        return tuple(prioritized[: self.max_categories])

    @staticmethod
    def _fallback_category_codes() -> Tuple[Tuple[str, str], ...]:
        return (
            ("1027", "Salata Malzemeleri"),
            ("1035", "Ayiklanmis Sebzeler"),
            ("1033", "Patates Sogan ve Sarimsak"),
            ("1313", "Uzun Omurlu Sut"),
            ("1319", "Beyaz Peynir"),
            ("1324", "Kasar Peynir"),
            ("1391", "Sade Yogurt"),
            ("1123", "Makarna"),
            ("1112", "Aycicek Yagi"),
            ("1181", "Domates Salcasi"),
            ("1459", "Siyah Cay"),
            ("1450", "Soguk Cay"),
            ("1419", "Kola"),
            ("1411", "Su"),
            ("1506", "Sutlu Cikolata"),
            ("1530", "Kremali Biskuvi"),
            ("1553", "Patates Cipsi"),
            ("1724", "Bulasik Makinesi Deterjani"),
            ("1752", "Camasir Yumusatici"),
            ("1775", "Tuvalet Kagidi"),
            ("1824", "Sampuan"),
            ("1853", "Dis Macunu"),
        )

    def _fetch_category_page(self, category_code: str, page: int) -> Optional[BeautifulSoup]:
        q_value = f":relevance:productPrimaryCategoryCode:{category_code}"
        if page <= 1:
            url = f"{self.base_url}/search?q={quote(q_value, safe=':')}"
        else:
            url = f"{self.base_url}/search?q={quote(q_value, safe=':')}&page={page}&isScroll=true"
        response = self._safe_get(url)
        if response is None:
            return None
        return BeautifulSoup(response.text, "html.parser")

    def _safe_get(self, url: str) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.request_timeout)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    def _parse_card(self, card: Tag, fallback_category: str) -> Optional[RawOffer]:
        data_layer = card.select_one(".dataLayerItemData")
        name_tag = card.select_one("h3.item-name")
        link_tag = card.select_one("a.product-return[href]")
        if data_layer is None or name_tag is None or link_tag is None:
            return None

        product_id = self._clean_text(data_layer.get("data-item_id"))
        name = self._clean_text(name_tag.get_text(" ", strip=True))
        current_price = self._price_from_card(card)
        if not product_id or not name or current_price is None or current_price <= 0:
            return None

        first_price = self._coerce_price(data_layer.get("data-first_price"))
        listed_price = first_price if first_price and first_price >= current_price else current_price
        promo_price = current_price if listed_price > current_price else None

        brand = self._clean_text(data_layer.get("data-item_brand"))
        if brand and (brand.startswith("BRN-") or brand.upper() == "MARKASIZ"):
            brand = None

        unit_label = self._clean_text(data_layer.get("data-item_variant")) or self._clean_text(
            (card.select_one("input[name='displayUnit']") or {}).get("value")
        )
        stock_status = "in_stock" if data_layer.get("data-in_stock") == "true" else "out_of_stock"
        image_url = self._image_url(card)
        product_url = urljoin(self.base_url, link_tag.get("href") or "")
        category = (
            self._clean_text(data_layer.get("data-item_category3"))
            or self._clean_text(data_layer.get("data-item_category2"))
            or self._clean_text(data_layer.get("data-item_category"))
            or fallback_category
        )

        payload = {
            "category_code": self._clean_text((card.select_one("input[name='productCategoryCodePost']") or {}).get("value")),
            "main_category": self._clean_text((card.select_one("input[name='productMainCategoryPost']") or {}).get("value")),
            "product_url": product_url,
            "data_discount": self._clean_text(data_layer.get("data-discount")),
            "product_limit": self._clean_text(data_layer.get("data-product_limit")),
        }

        return RawOffer(
            source_product_id=product_id,
            source_category=category or fallback_category,
            source_name=name,
            source_brand=brand,
            source_size=unit_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=stock_status,
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
            source_barcode=None,
        )

    @staticmethod
    def _image_url(card: Tag) -> Optional[str]:
        image = card.select_one("img[itemprop='image'], img")
        if image is None:
            return None
        return CarrefourAdapter._clean_text(image.get("data-src") or image.get("src"))

    @staticmethod
    def _price_from_card(card: Tag) -> Optional[float]:
        discounted = card.select_one(".item-price.js-variant-discounted-price")
        if discounted is not None:
            content_price = CarrefourAdapter._coerce_price(discounted.get("content"))
            if content_price is not None:
                return content_price
            text_price = CarrefourAdapter._parse_display_price(discounted.get_text(" ", strip=True))
            if text_price is not None:
                return text_price
        regular = card.select_one(".priceLineThrough.js-variant-price")
        if regular is not None:
            return CarrefourAdapter._parse_display_price(regular.get_text(" ", strip=True))
        return None

    @staticmethod
    def _parse_display_price(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        matches = re.findall(r"\d+(?:[.,]\d+)?", value.replace(" ", ""))
        if not matches:
            return None
        if len(matches) >= 2 and len(matches[-1]) == 2:
            whole = "".join(matches[:-1]).replace(".", "").replace(",", "")
            decimal = matches[-1]
            try:
                return float(f"{whole}.{decimal}")
            except ValueError:
                return None
        try:
            return float(matches[-1].replace(".", "").replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _coerce_price(value: Optional[object]) -> Optional[float]:
        if value in {None, ""}:
            return None
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_text(value: Optional[object]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned:
            return None
        return cleaned
