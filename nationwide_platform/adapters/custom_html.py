import html
import json
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from .base import FetchContext, MarketAdapter, RawOffer
from .http_fallback import curl_get


class HtmlStorefrontAdapter(MarketAdapter):
    market_key = "html_storefront"
    base_url = ""

    def __init__(self, request_timeout: int = 15, max_retries: int = 1):
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

    def _safe_post(self, url: str, data: dict) -> Optional[requests.Response]:
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                return self.session.post(url, data=data, timeout=self.request_timeout)
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            return None
        return None

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        matches = re.findall(r"\d+(?:[.,]\d+)?", text)
        if not matches:
            return None
        try:
            return float(matches[-1].replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _parse_price_values(text: str) -> Tuple[Optional[float], Optional[float]]:
        matches = re.findall(r"\d+(?:[.,]\d+)?", text)
        if not matches:
            return None, None
        values = []
        for match in matches:
            try:
                values.append(float(match.replace(",", ".")))
            except ValueError:
                continue
        if not values:
            return None, None
        if len(values) == 1:
            return values[0], None
        listed_price = values[-1]
        old_price = values[-2]
        if old_price > listed_price:
            return listed_price, old_price
        return listed_price, None

    @staticmethod
    def _clean_text(text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        cleaned = " ".join(text.split())
        return cleaned or None


class WooCommerceHtmlAdapter(HtmlStorefrontAdapter):
    market_key = "woocommerce_html"
    shop_path = "/shop/"

    def __init__(self, max_products: int = 5000, max_pages: int = 100, request_timeout: int = 15, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products
        self.max_pages = max_pages

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for page in range(1, self.max_pages + 1):
            response = self._safe_get(self._page_url(page))
            if response is None:
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select("li.product")
            if not cards:
                break
            for card in cards:
                offer = self._parse_card(card)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _page_url(self, page: int) -> str:
        normalized_shop_path = self.shop_path.strip("/")
        if page == 1:
            return urljoin(self.base_url, f"{normalized_shop_path}/")
        return urljoin(self.base_url, f"{normalized_shop_path}/page/{page}/")

    def _parse_card(self, card: Tag) -> Optional[RawOffer]:
        product_link = card.select_one("a.woocommerce-LoopProduct-link[href]")
        title_tag = card.select_one("h2.woocommerce-loop-product__title")
        price_container = card.select_one(".product-footer .price") or card.select_one(".product-body .price") or card.select_one(".price")
        if product_link is None or title_tag is None or price_container is None:
            return None

        name = self._clean_text(title_tag.get_text(" ", strip=True))
        if not name:
            return None

        current_price, old_price = self._parse_price_values(price_container.get_text(" ", strip=True))
        if current_price is None or current_price <= 0:
            return None

        add_to_cart = card.select_one(".add_to_cart_button[data-product_id]")
        source_product_id = (add_to_cart.get("data-product_id") if add_to_cart is not None else None) or self._fallback_product_id(card, product_link)
        if source_product_id is None:
            return None

        image_tag = card.select_one("img")
        image_url = None
        if image_tag is not None:
            image_path = image_tag.get("data-src") or image_tag.get("src")
            if image_path and not image_path.startswith("data:image"):
                image_url = urljoin(self.base_url, image_path)

        category_name = self._category_from_card(card)
        promo_price = current_price if old_price and old_price > current_price else None
        listed_price = old_price if old_price and old_price > current_price else current_price
        payload = {
            "url": urljoin(self.base_url, product_link.get("href") or ""),
            "category": category_name,
        }

        return RawOffer(
            source_product_id=str(source_product_id),
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=self._stock_status(card),
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _fallback_product_id(card: Tag, product_link: Tag) -> Optional[str]:
        for class_name in card.get("class") or []:
            if class_name.startswith("post-"):
                return class_name.split("post-", 1)[1]
        href = product_link.get("href") or ""
        slug = href.strip("/").split("/")[-1]
        return slug or None

    @staticmethod
    def _stock_status(card: Tag) -> str:
        class_names = set(card.get("class") or [])
        if "instock" in class_names:
            return "in_stock"
        if "outofstock" in class_names:
            return "out_of_stock"
        return "unknown"

    @staticmethod
    def _category_from_card(card: Tag) -> str:
        for class_name in card.get("class") or []:
            if class_name.startswith("product_cat-"):
                return class_name.split("product_cat-", 1)[1].replace("-", " ")
        return "Genel"


class TSoftCategoryAdapter(HtmlStorefrontAdapter):
    market_key = "tsoft_category"
    category_paths: Tuple[str, ...] = tuple()

    def __init__(self, max_products: int = 5000, request_timeout: int = 15, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        category_paths = self.category_paths or ("/",)
        for category_path in category_paths:
            response = self._safe_get(urljoin(self.base_url, category_path))
            if response is None:
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            category_name = self._category_name(soup, category_path)
            for card in soup.select("[data-toggle='product']"):
                offer = self._parse_card(card, category_name)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _category_name(self, soup: BeautifulSoup, category_path: str) -> str:
        heading = soup.select_one("h1")
        if heading is not None:
            name = self._clean_text(heading.get_text(" ", strip=True))
            if name:
                return name
        slug = category_path.strip("/").split("/")[-1] or "genel"
        return slug.replace("-", " ").title()

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        product_link = card.select_one("[data-toggle='product-url'][href]")
        title_tag = card.select_one("[data-toggle='product-title']")
        price_container = card.select_one("[data-qa='product-price']")
        if product_link is None or title_tag is None or price_container is None:
            return None

        name = self._clean_text(title_tag.get_text(" ", strip=True))
        if not name:
            return None

        current_price, old_price = self._parse_price_values(price_container.get_text(" ", strip=True))
        if current_price is None or current_price <= 0:
            return None

        source_product_id = card.get("data-id") or product_link.get("href", "").strip("/").split("/")[-1]
        if not source_product_id:
            return None

        image_tag = card.select_one("[data-toggle='product-image']")
        image_url = None
        if image_tag is not None:
            image_path = image_tag.get("data-src") or image_tag.get("src")
            if image_path:
                image_url = urljoin(self.base_url, image_path)

        payload = {
            "url": urljoin(self.base_url, product_link.get("href") or ""),
            "category": category_name,
        }
        promo_price = current_price if old_price and old_price > current_price else None
        listed_price = old_price if old_price and old_price > current_price else current_price

        return RawOffer(
            source_product_id=str(source_product_id),
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=self._stock_status(card),
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _stock_status(card: Tag) -> str:
        card_text = card.get_text(" ", strip=True).lower()
        if "tukendi" in card_text:
            return "out_of_stock"
        return "unknown"


class TSoftLegacyGridAdapter(HtmlStorefrontAdapter):
    market_key = "tsoft_legacy_grid"
    category_paths: Tuple[str, ...] = tuple()

    def __init__(self, max_products: int = 5000, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_path in self.category_paths:
            html_text = self._fetch_html(category_path)
            if not html_text:
                continue
            soup = BeautifulSoup(html_text, "html.parser")
            product_data = self._extract_product_data(html_text)
            category_name = self._category_name(category_path)
            cards = soup.select("div.productItem")
            if not cards:
                continue
            for card in cards:
                offer = self._parse_card(card, category_name, product_data)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _fetch_html(self, category_path: str) -> Optional[str]:
        url = urljoin(self.base_url, category_path)
        response = self._safe_get(url)
        if response is not None:
            response.raise_for_status()
            response.encoding = "utf-8"
            if "productItem" in response.text:
                return response.text
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
                    url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and "productItem" in completed.stdout:
                return completed.stdout
        return None

    @staticmethod
    def _extract_product_data(html_text: str) -> Dict[str, Dict[str, object]]:
        products: Dict[str, Dict[str, object]] = {}
        for raw_payload in re.findall(r"PRODUCT_DATA\.push\(JSON\.parse\('(.*?)'\)\);", html_text):
            try:
                decoded_payload = bytes(raw_payload, "utf-8").decode("unicode_escape")
                product = json.loads(decoded_payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            product_id = str(product.get("id") or "").strip()
            if product_id:
                products[product_id] = product
        return products

    @staticmethod
    def _category_name(category_path: str) -> str:
        slug = category_path.strip("/").split("/")[-1] or "genel"
        return slug.replace("-", " ").title()

    def _parse_card(
        self,
        card: Tag,
        fallback_category_name: str,
        product_data: Dict[str, Dict[str, object]],
    ) -> Optional[RawOffer]:
        title_anchor = card.select_one("a.vitrin-urun-adi[href]") or card.select_one("a.detailLink[href]")
        price_tag = card.select_one(".currentPrice")
        if title_anchor is None or price_tag is None:
            return None

        name = self._clean_text(title_anchor.get_text(" ", strip=True))
        current_price = self._parse_price(price_tag.get_text(" ", strip=True))
        if not name or current_price is None or current_price <= 0:
            return None

        href = title_anchor.get("href") or ""
        source_product_id = self._product_id_from_card(card, href)
        if source_product_id is None:
            return None

        product = product_data.get(source_product_id, {})
        category_name = self._clean_text(str(product.get("category") or "")) or fallback_category_name
        brand_name = self._clean_text(str(product.get("brand") or "")) or self._brand_from_card(card)
        size_label = self._size_from_card(card)
        listed_price = self._coerce_float(product.get("total_base_price")) or current_price
        promo_price = None

        sale_price = self._coerce_float(product.get("sale_price"))
        if listed_price > current_price:
            promo_price = current_price
        elif sale_price is not None and listed_price > sale_price:
            promo_price = sale_price

        image_url = self._image_url(card, product)
        payload = {
            "url": urljoin(self.base_url, str(product.get("url") or href)),
            "category": category_name,
            "card_price": current_price,
            "quantity": product.get("quantity"),
        }

        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=brand_name,
            source_size=size_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=self._stock_status(card, product),
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _coerce_float(value: object) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(",", "."))
            except ValueError:
                return None
        return None

    @staticmethod
    def _product_id_from_card(card: Tag, href: str) -> Optional[str]:
        add_to_cart = card.select_one("[onclick*='Add2Cart']")
        if add_to_cart is not None:
            onclick = add_to_cart.get("onclick") or ""
            match = re.search(r"Add2Cart\((\d+)", onclick)
            if match:
                return match.group(1)
        hidden_input = card.select_one("input.myProductList[value]")
        if hidden_input is not None:
            value = hidden_input.get("value")
            if value:
                return value
        slug = href.strip("/").split("/")[-1]
        return slug or None

    def _brand_from_card(self, card: Tag) -> Optional[str]:
        brand_tag = card.select_one("a.vitrin-marka")
        if brand_tag is None:
            return None
        return self._clean_text(brand_tag.get_text(" ", strip=True))

    def _size_from_card(self, card: Tag) -> Optional[str]:
        unit_tag = card.select_one(".kgChange")
        if unit_tag is None:
            return None
        return self._clean_text(unit_tag.get_text(" ", strip=True))

    def _image_url(self, card: Tag, product: Dict[str, object]) -> Optional[str]:
        image_value = product.get("image")
        if isinstance(image_value, str) and image_value.strip():
            return self._clean_text(image_value)

        image_tag = card.select_one("img.stImage")
        image_path = None
        if image_tag is not None:
            image_path = image_tag.get("data-src") or image_tag.get("src")
        if image_path and not image_path.startswith("data:image"):
            return urljoin(self.base_url, image_path)
        return None

    def _stock_status(self, card: Tag, product: Dict[str, object]) -> str:
        quantity = self._coerce_float(product.get("quantity"))
        if quantity is not None:
            return "in_stock" if quantity > 0 else "out_of_stock"
        card_text = card.get_text(" ", strip=True).lower()
        if "stokta yok" in card_text or "tukendi" in card_text:
            return "out_of_stock"
        if card.select_one("[onclick*='Add2Cart']") is not None:
            return "in_stock"
        return "unknown"


class GelsineveCatalogAdapter(HtmlStorefrontAdapter):
    market_key = "gelsineve_catalog"
    category_paths: Tuple[str, ...] = tuple()

    def __init__(self, max_products: int = 5000, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_path in self.category_paths:
            html_text = self._fetch_html(category_path)
            if not html_text:
                continue
            soup = BeautifulSoup(html_text, "html.parser")
            category_name = self._category_name(category_path)
            for card in soup.select(".product"):
                offer = self._parse_card(card, category_name)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _fetch_html(self, category_path: str) -> Optional[str]:
        url = urljoin(self.base_url, category_path)
        response = self._safe_get(url)
        if response is not None:
            response.raise_for_status()
            response.encoding = "utf-8"
            if 'class="product"' in response.text:
                return response.text
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
                    url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and 'class="product"' in completed.stdout:
                return completed.stdout
        return None

    @staticmethod
    def _category_name(category_path: str) -> str:
        slug = category_path.strip("/").split("/")[-1]
        category_part = slug.split("-1-c-", 1)[0] if "-1-c-" in slug else slug
        return category_part.replace("-", " ").title() or "Genel"

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        title_anchor = card.select_one(".urunAciklama h3 a[href]") or card.select_one(".product-info h3 a[href]")
        price_tag = card.select_one(".new-price")
        if title_anchor is None or price_tag is None:
            return None

        href = title_anchor.get("href") or ""
        product_id = self._product_id_from_href(href)
        name = self._clean_text(title_anchor.get_text(" ", strip=True))
        current_price = self._parse_price(price_tag.get_text(" ", strip=True))
        if product_id is None or not name or current_price is None or current_price <= 0:
            return None

        old_price_tag = card.select_one(".old-price")
        old_price = self._parse_price(old_price_tag.get_text(" ", strip=True)) if old_price_tag is not None else None
        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None

        unit_tag = card.select_one(".birimText")
        image_tag = card.select_one(".product-image img[src]") or card.select_one("img[src]")
        image_url = urljoin(self.base_url, image_tag.get("src")) if image_tag is not None and image_tag.get("src") else None

        payload = {
            "url": urljoin(self.base_url, href),
            "category": category_name,
        }

        return RawOffer(
            source_product_id=product_id,
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=self._clean_text(unit_tag.get_text(" ", strip=True) if unit_tag is not None else None),
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=self._stock_status(card),
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _product_id_from_href(href: str) -> Optional[str]:
        match = re.search(r"-p-(\d+)", href)
        if match:
            return match.group(1)
        slug = href.strip("/").split("/")[-1]
        return slug or None

    def _stock_status(self, card: Tag) -> str:
        text = card.get_text(" ", strip=True).lower()
        if "stokta yok" in text or "tukendi" in text:
            return "out_of_stock"
        if "sepete ekle" in text:
            return "in_stock"
        return "unknown"


class OpenCartSearchAdapter(HtmlStorefrontAdapter):
    market_key = "opencart_search"
    seed_queries: Tuple[str, ...] = ("domates", "sut", "peynir", "deterjan", "makarna")

    def __init__(self, max_products: int = 5000, request_timeout: int = 15, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for query in self.seed_queries:
            response = self._safe_get(self._search_url(query))
            if response is None:
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select(".product-layout .product-thumb"):
                offer = self._parse_card(card, query.title())
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _search_url(self, query: str) -> str:
        params = urlencode({"route": "product/search", "search": query})
        return urljoin(self.base_url, f"/index.php?{params}")

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        product_link = card.select_one(".caption h4 a[href]") or card.select_one(".name a[href]") or card.select_one(".image a[href]")
        price_container = card.select_one(".price")
        if product_link is None or price_container is None:
            return None

        name = self._clean_text(product_link.get_text(" ", strip=True))
        if not name:
            return None

        current_price = self._parse_price((price_container.select_one(".price-new") or price_container).get_text(" ", strip=True))
        old_price_tag = price_container.select_one(".price-old")
        old_price = self._parse_price(old_price_tag.get_text(" ", strip=True)) if old_price_tag is not None else None
        if current_price is None or current_price <= 0:
            return None

        href = product_link.get("href") or ""
        source_product_id = self._extract_product_id(card, href)
        if source_product_id is None:
            return None

        image_tag = card.select_one(".image img[src]") or card.select_one("img[src]")
        image_url = None
        if image_tag is not None and image_tag.get("src"):
            image_url = urljoin(self.base_url, image_tag.get("src"))

        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None
        payload = {
            "url": urljoin(self.base_url, href),
            "search_query": category_name,
        }

        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=self._stock_status_from_card(card),
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _extract_product_id(card: Tag, href: str) -> Optional[str]:
        button = card.select_one("button[onclick*='cart.add']")
        if button is not None:
            onclick = button.get("onclick") or ""
            match = re.search(r"cart\.add\('(\d+)'", onclick)
            if match:
                return match.group(1)
        match = re.search(r"product_id=(\d+)", href)
        if match:
            return match.group(1)
        slug = href.strip("/").split("/")[-1]
        return slug or None

    @staticmethod
    def _stock_status_from_card(card: Tag) -> str:
        button = card.select_one("button[onclick*='cart.add']")
        if button is not None:
            return "in_stock"
        card_text = card.get_text(" ", strip=True).lower()
        if "stokta yok" in card_text or "tukendi" in card_text:
            return "out_of_stock"
        return "unknown"


class EskisehirMarketCategoryAdapter(HtmlStorefrontAdapter):
    market_key = "eskisehir_market"
    base_url = "https://eskisehirmarket.com"
    category_paths: Tuple[str, ...] = (
        "/kategori/kisisel-bakim-34",
        "/kategori/ev-yasam-33",
        "/kategori/elektronik-32",
        "/kategori/erkek-giyim-2",
        "/kategori/kadin-giyim-12",
    )

    def __init__(self, max_products: int = 5000, request_timeout: int = 15, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_path in self.category_paths:
            response = self._safe_get(urljoin(self.base_url, category_path))
            if response is None:
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            category_name = self._category_name(soup, category_path)
            for card in soup.select(".urun"):
                offer = self._parse_card(card, category_name)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _category_name(self, soup: BeautifulSoup, category_path: str) -> str:
        heading = soup.select_one("title") or soup.select_one("h1")
        if heading is not None:
            name = self._clean_text(heading.get_text(" ", strip=True))
            if name:
                return name
        slug = category_path.strip("/").split("/")[-1]
        return slug.rsplit("-", 1)[0].replace("-", " ").title()

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        product_link = card.select_one("a.link[href]") or card.select_one("a[href][title]")
        image_tag = card.select_one("img[src]")
        price_box = card.select_one(".fiyat")
        if product_link is None or price_box is None:
            return None

        name = self._clean_text(product_link.get_text(" ", strip=True)) or self._clean_text(product_link.get("title"))
        if not name:
            return None

        current_tag = price_box.select_one(".guncel")
        old_tag = price_box.select_one(".eski span")
        current_price = self._parse_price(current_tag.get_text(" ", strip=True) if current_tag is not None else price_box.get_text(" ", strip=True))
        old_price = self._parse_price(old_tag.get_text(" ", strip=True)) if old_tag is not None else None
        if current_price is None or current_price <= 0:
            return None

        href = product_link.get("href") or ""
        source_product_id = self._extract_product_id(href)
        if source_product_id is None:
            return None

        image_url = None
        if image_tag is not None and image_tag.get("src"):
            image_url = urljoin(self.base_url, image_tag.get("src"))

        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None
        payload = {
            "url": urljoin(self.base_url, href),
            "category": category_name,
        }
        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="in_stock",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _extract_product_id(href: str) -> Optional[str]:
        match = re.search(r"-(\d+)$", href)
        if match:
            return match.group(1)
        slug = href.strip("/").split("/")[-1]
        return slug or None


class PrestaShopElementorCatalogAdapter(HtmlStorefrontAdapter):
    market_key = "prestashop_elementor_catalog"
    category_paths: Tuple[str, ...] = tuple()

    def __init__(
        self,
        max_products: int = 5000,
        max_pages_per_category: int = 50,
        request_timeout: int = 15,
        max_retries: int = 1,
    ):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products
        self.max_pages_per_category = max_pages_per_category

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        product_refs: List[Dict[str, str]] = []
        seen_ids = set()
        for category_path in self.category_paths or ("/",):
            for page in range(1, self.max_pages_per_category + 1):
                response = self._safe_get(self._category_page_url(category_path, page))
                if response is None:
                    continue
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.select("#js-product-list article[data-id-product]")
                if not cards:
                    break
                category_name = self._category_name(soup, category_path)
                for card in cards:
                    product_ref = self._parse_listing_card(card, category_name)
                    if product_ref is None:
                        continue
                    product_id = product_ref["source_product_id"]
                    if product_id in seen_ids:
                        continue
                    seen_ids.add(product_id)
                    product_refs.append(product_ref)
                    if len(product_refs) >= self.max_products:
                        return self._hydrate_product_refs(product_refs)
        return self._hydrate_product_refs(product_refs)

    def _category_page_url(self, category_path: str, page: int) -> str:
        normalized_path = category_path if category_path.startswith("/") else f"/{category_path}"
        if page == 1:
            return urljoin(self.base_url, normalized_path)
        separator = "&" if "?" in normalized_path else "?"
        return urljoin(self.base_url, f"{normalized_path}{separator}page={page}")

    def _category_name(self, soup: BeautifulSoup, category_path: str) -> str:
        heading = soup.select_one("h1")
        if heading is not None:
            name = self._clean_text(heading.get_text(" ", strip=True))
            if name:
                return name
        if soup.title is not None:
            title = self._clean_text(soup.title.get_text(" ", strip=True))
            if title:
                return title.replace(" - K-depo", "")
        slug = category_path.strip("/").split("/")[-1] or "genel"
        return slug.replace("-", " ").title()

    def _parse_listing_card(self, card: Tag, category_name: str) -> Optional[Dict[str, str]]:
        product_id = card.get("data-id-product")
        name_anchor = card.select_one("h3.ce-product-name a[href]")
        if product_id is None or name_anchor is None:
            return None

        product_url = urljoin(self.base_url, name_anchor.get("href") or "")
        if not product_url:
            return None

        image_tag = card.select_one(".elementor-image img[src]")
        image_url = None
        if image_tag is not None and image_tag.get("src"):
            image_url = urljoin(self.base_url, image_tag.get("src"))

        return {
            "source_product_id": str(product_id),
            "product_url": product_url,
            "category_name": category_name,
            "image_url": image_url or "",
        }

    def _hydrate_product_refs(self, product_refs: List[Dict[str, str]]) -> List[RawOffer]:
        offers: List[RawOffer] = []
        for product_ref in product_refs:
            response = self._safe_get(product_ref["product_url"])
            if response is None:
                continue
            response.raise_for_status()
            offer = self._parse_product_detail(response.text, product_ref)
            if offer is not None:
                offers.append(offer)
        return offers

    def _parse_product_detail(self, html_text: str, product_ref: Dict[str, str]) -> Optional[RawOffer]:
        soup = BeautifulSoup(html_text, "html.parser")
        product_root = soup.select_one("#product-details[data-product]")
        if product_root is None:
            return None

        raw_payload = html.unescape(product_root.get("data-product") or "")
        if not raw_payload:
            return None

        try:
            product = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None

        name = self._clean_text(product.get("name"))
        if not name:
            return None

        current_price = self._coerce_float(product.get("price_amount"))
        if current_price is None:
            current_price = self._parse_price(str(product.get("price") or ""))
        if current_price is None or current_price <= 0:
            return None

        price_without_reduction = self._coerce_float(product.get("price_without_reduction"))
        has_discount = bool(product.get("has_discount")) and price_without_reduction and price_without_reduction > current_price
        listed_price = price_without_reduction if has_discount else current_price
        promo_price = current_price if has_discount else None

        image_url = product_ref.get("image_url") or None
        cover = product.get("cover")
        if isinstance(cover, dict):
            large = cover.get("large")
            medium = cover.get("medium")
            if isinstance(large, dict) and large.get("url"):
                image_url = urljoin(self.base_url, large["url"])
            elif isinstance(medium, dict) and medium.get("url"):
                image_url = urljoin(self.base_url, medium["url"])

        category_name = self._clean_text(product.get("category_name")) or product_ref["category_name"]
        payload = {
            "url": product.get("link") or product_ref["product_url"],
            "category": category_name,
            "quantity": product.get("quantity"),
            "has_discount": bool(product.get("has_discount")),
            "minimum_quantity": product.get("minimal_quantity"),
        }

        return RawOffer(
            source_product_id=str(product.get("id_product") or product.get("id") or product_ref["source_product_id"]),
            source_category=category_name,
            source_name=name,
            source_brand=self._clean_text(product.get("manufacturer_name")),
            source_size=self._source_size(product),
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status=self._stock_status(product),
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

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

    def _source_size(self, product: Dict[str, object]) -> Optional[str]:
        weight_value = self._coerce_float(product.get("weight"))
        if weight_value is None or weight_value <= 0:
            return None
        if weight_value < 1:
            grams = int(round(weight_value * 1000))
            return f"{grams} gr"
        if weight_value.is_integer():
            return f"{int(weight_value)} kg"
        return f"{weight_value:.2f} kg"

    def _stock_status(self, product: Dict[str, object]) -> str:
        quantity = self._coerce_float(product.get("quantity"))
        if quantity is None:
            return "unknown"
        if quantity > 0:
            return "in_stock"
        return "out_of_stock"


class WixStoresCategoryAdapter(HtmlStorefrontAdapter):
    market_key = "wix_stores"
    category_paths: Tuple[str, ...] = ("/",)

    def __init__(self, max_products: int = 5000, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_path in self._iter_category_paths():
            response = self._safe_get(urljoin(self.base_url, category_path))
            if response is None:
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            category_name = self._category_name(category_path)
            cards = soup.select("[data-hook='product-item-root']")
            if not cards:
                continue
            for card in cards:
                offer = self._parse_card(card, category_name)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _iter_category_paths(self) -> Tuple[str, ...]:
        discovered = self._discover_category_paths()
        if discovered:
            return discovered
        return self.category_paths or ("/",)

    def _discover_category_paths(self) -> Tuple[str, ...]:
        return tuple(path for path in self.category_paths if path)

    @staticmethod
    def _category_name(category_path: str) -> str:
        if category_path == "/":
            return "Genel"
        slug = category_path.strip("/").split("/")[-1] or "genel"
        return slug.replace("-", " ").title()

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        name_tag = card.select_one("[data-hook='product-item-name']")
        price_tag = card.select_one("[data-hook='product-item-price-to-pay']")
        link_tag = card.select_one("a[data-hook='product-item-product-details-link'][href]") or card.select_one(
            "a[data-hook='product-item-container'][href]"
        )
        if name_tag is None or price_tag is None or link_tag is None:
            return None

        name = self._clean_text(name_tag.get_text(" ", strip=True))
        current_price = self._parse_price(price_tag.get_text(" ", strip=True))
        href = link_tag.get("href") or ""
        source_product_id = card.get("data-slug") or href.rstrip("/").split("/")[-1]
        if not name or current_price is None or current_price <= 0 or not source_product_id:
            return None

        image_tag = card.select_one("img[src]")
        image_url = None
        if image_tag is not None and image_tag.get("src"):
            image_url = urljoin(self.base_url, image_tag.get("src"))

        payload = {
            "url": urljoin(self.base_url, href),
            "category": category_name,
        }

        return RawOffer(
            source_product_id=str(source_product_id),
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=current_price,
            promo_price=None,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )


class ShowcaseCategoryAdapter(HtmlStorefrontAdapter):
    market_key = "showcase_category"
    category_paths: Tuple[str, ...] = tuple()

    def __init__(self, max_products: int = 250, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_path in self._iter_category_paths():
            html_text = self._fetch_html(category_path)
            if not html_text:
                continue
            soup = BeautifulSoup(html_text, "html.parser")
            category_name = self._category_name(category_path)
            cards = soup.select(".showcase")
            if not cards:
                continue
            for card in cards:
                offer = self._parse_card(card, category_name)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _iter_category_paths(self) -> Tuple[str, ...]:
        discovered = self._discover_category_paths()
        if discovered:
            return discovered
        return self.category_paths or ("/",)

    def _discover_category_paths(self) -> Tuple[str, ...]:
        return tuple(path for path in self.category_paths if path)

    def _fetch_html(self, category_path: str) -> Optional[str]:
        url = urljoin(self.base_url, category_path)
        response = self._safe_get(url)
        if response is not None:
            response.raise_for_status()
            if ".showcase-title" in response.text or "data-product-id" in response.text:
                return response.text
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
                    url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and ("showcase-title" in completed.stdout or "data-product-id" in completed.stdout):
                return completed.stdout
        return None

    @staticmethod
    def _category_name(category_path: str) -> str:
        slug = category_path.strip("/").split("/")[-1] or "genel"
        return slug.replace("-", " ").title()

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        title_anchor = card.select_one(".showcase-title a[href]")
        price_tag = card.select_one(".showcase-price-new")
        add_to_cart = card.select_one("[data-product-id]")
        if title_anchor is None or price_tag is None or add_to_cart is None:
            return None

        name = self._clean_text(title_anchor.get_text(" ", strip=True))
        current_price = self._parse_price(price_tag.get_text(" ", strip=True))
        source_product_id = add_to_cart.get("data-product-id") or title_anchor.get("href", "").strip("/").split("/")[-1]
        if not name or current_price is None or current_price <= 0 or not source_product_id:
            return None

        unit_tag = price_tag.select_one("span")
        unit_label = self._clean_text(unit_tag.get_text(" ", strip=True)) if unit_tag is not None else None

        image_tag = card.select_one(".showcase-image img")
        image_url = None
        if image_tag is not None:
            image_path = image_tag.get("data-src") or image_tag.get("src")
            if image_path:
                image_url = urljoin(self.base_url, image_path)

        href = title_anchor.get("href") or ""
        payload = {
            "url": urljoin(self.base_url, href),
            "category": category_name,
        }

        return RawOffer(
            source_product_id=str(source_product_id),
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=unit_label,
            listed_price=current_price,
            promo_price=None,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )


class AyaydinGrossAdapter(HtmlStorefrontAdapter):
    market_key = "ayaydin_gross_erzincan"
    base_url = "https://ayaydingrossmarket.com"

    def __init__(self, max_products: int = 120, request_timeout: int = 15, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        response = self._safe_get(self.base_url)
        if response is None:
            return []
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        tab_names = self._tab_names(soup)

        offers: List[RawOffer] = []
        seen_ids = set()
        for listing in soup.select("ul[class*='tab-product-list']"):
            category = tab_names.get(listing.get("data-tab-id"), "Genel")
            for card in listing.select(".product-item"):
                offer = self._parse_card(card, category)
                if offer is None:
                    continue
                if offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _tab_names(self, soup: BeautifulSoup) -> Dict[str, str]:
        names: Dict[str, str] = {}
        for tab in soup.select("a[id^='product-slider-tab-'][href^='#product-slider-tab-content-']"):
            href = tab.get("href") or ""
            tab_id = href.split("product-slider-tab-content-")[-1]
            names[tab_id] = self._clean_text(tab.get_text(" ", strip=True)) or "Genel"
        return names

    def _parse_card(self, card: Tag, category: str) -> Optional[RawOffer]:
        name_anchor = card.select_one(".product-name a")
        price_container = card.select_one(".product-price")
        if name_anchor is None or price_container is None:
            return None

        name = self._clean_text(name_anchor.get_text(" ", strip=True))
        if not name:
            return None

        current_price = self._parse_price((price_container.select_one(".price") or price_container).get_text(" ", strip=True))
        old_price_tag = price_container.select_one(".old-price")
        old_price = self._parse_price(old_price_tag.get_text(" ", strip=True)) if old_price_tag is not None else None
        if current_price is None or current_price <= 0:
            return None

        add_to_cart = card.select_one("[data-src*='ProductId=']")
        source_product_id = self._product_id_from_card(add_to_cart, name_anchor.get("href"))
        if source_product_id is None:
            return None

        image_tag = card.select_one("img")
        image_url = None
        if image_tag is not None:
            image_path = image_tag.get("data-src") or image_tag.get("src")
            if image_path:
                image_url = urljoin(self.base_url, image_path)

        payload = {
            "url": urljoin(self.base_url, name_anchor.get("href") or ""),
            "category": category,
            "product_id": source_product_id,
        }

        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None

        return RawOffer(
            source_product_id=source_product_id,
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

    @staticmethod
    def _product_id_from_card(add_to_cart: Optional[Tag], href: Optional[str]) -> Optional[str]:
        if add_to_cart is not None:
            query = parse_qs(urlparse(add_to_cart.get("data-src") or "").query)
            product_ids = query.get("ProductId")
            if product_ids:
                return product_ids[0]
        if href:
            cleaned = href.strip("/").split("/")[-1]
            return cleaned or None
        return None


class BasdasAdapter(HtmlStorefrontAdapter):
    market_key = "basdas_online_izmir"
    base_url = "https://basdasonline.com"

    def __init__(
        self,
        max_products: int = 5000,
        seed_queries: Tuple[str, ...] = (
            "domates",
            "peynir",
            "sut",
            "deterjan",
            "bebek",
            "makarna",
            "su",
            "cay",
            "kahve",
            "meyve",
            "sebze",
            "atistirmalik",
            "et",
            "tavuk",
            "balik",
            "yumurta",
            "yoğurt",
            "pirinç",
            "bakliyat",
            "makyaj",
            "şampuan",
            "kolonya",
            "çikolata",
            "çamaşır",
            "bulaşık",
            "oyuncak",
            "elektronik",
        ),
        request_timeout: int = 15,
        max_retries: int = 1,
    ):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products
        self.seed_queries = seed_queries

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for query in self.seed_queries:
            response = self._safe_post(
                f"{self.base_url}/arama_v3_urunler.asp",
                data={
                    "que": query,
                    "UrunListesi": "",
                    "StokDurum": "0",
                    "Siralama": "sonucfiyat-asc",
                    "type": "",
                    "cmpId": "",
                    "KutuGorunumu": "katalog",
                },
            )
            if response is None:
                continue
            response.raise_for_status()
            response.encoding = "utf-8"
            result_soup = BeautifulSoup(response.text, "html.parser")
            for card in result_soup.select(".urun-kutusu"):
                offer = self._parse_card(card, "Genel")
                if offer is None:
                    continue
                if offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        product_link = card.select_one("h2 a[href*='p-']") or card.select_one("a.kutu-link[href*='p-']")
        price_container = card.select_one(".urun-fiyat")
        if product_link is None or price_container is None:
            return None

        href = product_link.get("href") or ""
        product_id_match = re.search(r"p-(\d+)-", href)
        if not product_id_match:
            return None

        name = self._clean_text((card.select_one("h2 a") or product_link).get_text(" ", strip=True))
        if not name:
            return None

        listed_price, old_price = self._parse_price_values(price_container.get_text(" ", strip=True))
        if listed_price is None or listed_price <= 0:
            return None

        image_tag = card.select_one("img")
        image_url = urljoin(self.base_url, image_tag.get("src")) if image_tag and image_tag.get("src") else None
        payload = {
            "url": urljoin(self.base_url, href),
            "category": category_name,
        }

        promo_price = listed_price if old_price and old_price > listed_price else None
        resolved_listed = old_price if old_price and old_price > listed_price else listed_price

        return RawOffer(
            source_product_id=product_id_match.group(1),
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=resolved_listed,
            promo_price=promo_price,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )


class SitemapProductDetailAdapter(HtmlStorefrontAdapter):
    market_key = "sitemap_product_detail"
    sitemap_path = "/sitemap.xml"
    excluded_prefixes: Tuple[str, ...] = (
        "/urunler/",
        "/icerik/",
        "/marketlerimiz",
        "/hakkimizda",
        "/blog",
        "/iletisim",
        "/giris",
        "/sepetim",
        "/indirimler",
        "/teslimat-kosullari",
        "/gizlilik-politikasi",
    )

    def __init__(self, max_products: int = 5000, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        for url in self._product_links():
            html_text = self._fetch_text(url)
            if not html_text:
                continue
            offer = self._parse_product_page(url, html_text)
            if offer is None:
                continue
            offers.append(offer)
            if len(offers) >= self.max_products:
                break
        return offers

    def _product_links(self) -> List[str]:
        sitemap_url = urljoin(self.base_url, self.sitemap_path)
        sitemap_text = self._fetch_text(sitemap_url)
        if not sitemap_text:
            return []

        soup = BeautifulSoup(sitemap_text, "xml")
        product_links: List[str] = []
        seen_urls = set()
        for loc in soup.find_all("loc"):
            url = (loc.get_text(strip=True) or "").strip()
            if not self._is_product_url(url) or url in seen_urls:
                continue
            seen_urls.add(url)
            product_links.append(url)
            if len(product_links) >= self.max_products:
                break
        return product_links

    def _fetch_text(self, url: str) -> Optional[str]:
        response = self._safe_get(url)
        if response is not None and response.status_code == 200 and response.text:
            return response.text
        for _ in range(self.max_retries + 1):
            completed = subprocess.run(
                [
                    "curl",
                    "-k",
                    "-L",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    str(self.request_timeout),
                    "--url",
                    url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and completed.stdout:
                return completed.stdout
        return None

    def _is_product_url(self, url: str) -> bool:
        if not url.startswith(self.base_url):
            return False
        path = urlparse(url).path.rstrip("/")
        if not path:
            return False
        if any(path.startswith(prefix) for prefix in self.excluded_prefixes):
            return False
        slug = path.lstrip("/")
        if "/" in slug:
            return False
        return bool(re.search(r"-\d+$", slug))

    def _parse_product_page(self, url: str, html_text: str) -> Optional[RawOffer]:
        soup = BeautifulSoup(html_text, "html.parser")

        name_tag = soup.select_one("h1.product-name") or soup.select_one("h1")
        name = self._clean_text(name_tag.get_text(" ", strip=True) if name_tag is not None else None)
        if not name:
            return None

        schema = self._extract_product_schema(soup)
        current_price, old_price = self._extract_prices(soup, schema)
        if current_price is None or current_price <= 0:
            return None

        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None
        category_name = self._extract_category(soup, name)
        stock_status = self._extract_stock_status(soup)
        image_url = self._extract_image(soup, schema)
        brand = self._extract_brand(schema)
        barcode = self._extract_barcode(schema)
        source_product_id = self._product_id_from_url(url)

        payload = {
            "url": url,
            "category": category_name,
            "schema": schema,
        }

        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
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

    def _extract_product_schema(self, soup: BeautifulSoup) -> dict:
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
                if candidate.get("@type") == "Product" or candidate.get("offers"):
                    return candidate
        return {}

    def _extract_prices(self, soup: BeautifulSoup, schema: dict) -> Tuple[Optional[float], Optional[float]]:
        offers = schema.get("offers")
        if isinstance(offers, list):
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                current = self._parse_price(str(offer.get("lowPrice") or offer.get("price") or ""))
                old = self._parse_price(str(offer.get("highPrice") or ""))
                if current is not None:
                    return current, old
        elif isinstance(offers, dict):
            current = self._parse_price(str(offers.get("lowPrice") or offers.get("price") or ""))
            old = self._parse_price(str(offers.get("highPrice") or ""))
            if current is not None:
                return current, old

        price_tag = soup.select_one(".shop-detail_info .product-price")
        if price_tag is not None:
            current, old = self._parse_price_values(price_tag.get_text(" ", strip=True))
            if current is not None:
                return current, old

        for paragraph in soup.select(".description-item_text p"):
            text = paragraph.get_text(" ", strip=True)
            if "yerine" not in text.lower():
                continue
            values = re.findall(r"\d+(?:[.,]\d+)?", text)
            parsed_values = [self._parse_price(value) for value in values]
            filtered = [value for value in parsed_values if value is not None]
            if len(filtered) >= 2:
                return filtered[-1], filtered[-2]
            if filtered:
                return filtered[-1], None
        return None, None

    def _extract_category(self, soup: BeautifulSoup, product_name: str) -> str:
        breadcrumb_names = [
            self._clean_text(element.get_text(" ", strip=True))
            for element in soup.select(".ogami-breadcrumb a")
        ]
        filtered = [name for name in breadcrumb_names if name and name not in {"Anasayfa", product_name}]
        if filtered:
            return filtered[-1]
        return "Genel"

    def _extract_stock_status(self, soup: BeautifulSoup) -> str:
        stock_tag = soup.select_one(".shop-detail_info .product-type")
        stock_text = self._clean_text(stock_tag.get_text(" ", strip=True) if stock_tag is not None else None)
        if not stock_text:
            return "unknown"
        lowered = stock_text.lower()
        if "yok" in lowered or "tukendi" in lowered:
            return "out_of_stock"
        if "stokta" in lowered or "mevcut" in lowered:
            return "in_stock"
        return "unknown"

    def _extract_image(self, soup: BeautifulSoup, schema: dict) -> Optional[str]:
        image_tag = soup.select_one(".shop-detail_img img[src]")
        image_path = image_tag.get("src") if image_tag is not None else None
        if image_path:
            return urljoin(self.base_url, image_path)
        image_value = schema.get("image")
        if isinstance(image_value, list) and image_value:
            return self._clean_text(str(image_value[0]))
        if isinstance(image_value, str):
            return self._clean_text(image_value)
        return None

    @staticmethod
    def _extract_brand(schema: dict) -> Optional[str]:
        brand = schema.get("brand")
        if isinstance(brand, dict):
            return SitemapProductDetailAdapter._clean_text(brand.get("name"))
        if isinstance(brand, str):
            return SitemapProductDetailAdapter._clean_text(brand)
        return None

    @staticmethod
    def _extract_barcode(schema: dict) -> Optional[str]:
        for key in ("gtin13", "gtin", "sku", "mpn"):
            value = schema.get(key)
            cleaned = SitemapProductDetailAdapter._clean_text(str(value)) if value is not None else None
            if cleaned and re.fullmatch(r"\d{8,14}", cleaned):
                return cleaned
        return None

    @staticmethod
    def _product_id_from_url(url: str) -> str:
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        match = re.search(r"(\d+)$", slug)
        return match.group(1) if match else slug


class GuvendikAdapter(WooCommerceHtmlAdapter):
    market_key = "guvendik_erzurum"
    base_url = "https://www.guvendikmarket.com"


class AftaMarketAdapter(TSoftLegacyGridAdapter):
    market_key = "afta_market_giresun"
    base_url = "https://www.aftamarket.com.tr"
    category_paths = (
        "/meyve-sebze",
        "/sut-kahvaltilik",
        "/temizlik",
    )


class GelsineveOrduAdapter(GelsineveCatalogAdapter):
    market_key = "gelsineve_ordu"
    base_url = "https://www.gelsineve.com"
    category_paths = (
        "/kategoriler/meyve-sebze-1-c-1",
        "/kategoriler/sut-kahvaltilik-1-c-3",
        "/kategoriler/gida-sekerleme-1-c-4",
    )


class AnkamarGiresunAdapter(GelsineveCatalogAdapter):
    market_key = "ankamar_giresun"
    base_url = "https://www.gelsineve.com"
    category_paths = (
        "/kategoriler/meyve-sebze-1-c-1",
        "/kategoriler/sut-kahvaltilik-1-c-3",
        "/kategoriler/gida-sekerleme-1-c-4",
    )


class AnkamarOrduAdapter(GelsineveCatalogAdapter):
    market_key = "ankamar_ordu"
    base_url = "https://www.gelsineve.com"
    category_paths = (
        "/kategoriler/meyve-sebze-1-c-1",
        "/kategoriler/sut-kahvaltilik-1-c-3",
        "/kategoriler/gida-sekerleme-1-c-4",
    )


class KommerzCategoryAjaxAdapter(HtmlStorefrontAdapter):
    market_key = "kommerz_ajax"
    category_paths: Tuple[str, ...] = tuple()

    def __init__(self, max_products: int = 5000, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_path in self.category_paths:
            html_text = self._fetch_listing_html(category_path)
            if not html_text:
                continue
            soup = BeautifulSoup(html_text, "html.parser")
            category_name = self._category_name(category_path)
            for card in soup.select(".kutu-urun-border"):
                offer = self._parse_card(card, category_name)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _fetch_listing_html(self, category_path: str) -> Optional[str]:
        page_url = urljoin(self.base_url, category_path)
        response = self._safe_get(page_url)
        if response is None:
            return None
        response.raise_for_status()
        ajax_params = self._extract_ajax_params(response.text)
        if ajax_params is None:
            return None

        ajax_url = urljoin(self.base_url, f"secimi_daralt_urunler.asp?h={ajax_params['token']}")
        payload = {
            "KategoriId": ajax_params["category_id"],
            "UrunListesi": "",
            "StokDurum": "",
            "Siralama": "",
            "KutuGorunumu": "0",
        }
        return self._fetch_ajax_html(ajax_url=ajax_url, page_url=page_url, payload=payload)

    def _fetch_ajax_html(self, ajax_url: str, page_url: str, payload: Dict[str, str]) -> Optional[str]:
        headers = {
            "Referer": page_url,
            "X-Requested-With": "XMLHttpRequest",
        }
        for attempt in range(self.max_retries + 2):
            ajax_response = self.session.post(
                ajax_url,
                data=payload,
                headers=headers,
                timeout=self.request_timeout,
            )
            if ajax_response.status_code == 429:
                time.sleep(min(2.5, 0.8 * (attempt + 1)))
                continue
            ajax_response.raise_for_status()
            if "kutu-urun-border" in ajax_response.text:
                return ajax_response.text

        curl_command = [
            "curl",
            "-L",
            "--silent",
            "--show-error",
            "--max-time",
            str(self.request_timeout),
            "--user-agent",
            self.session.headers.get("User-Agent", "Mozilla/5.0"),
            "--referer",
            page_url,
            "--header",
            "X-Requested-With: XMLHttpRequest",
            "--request",
            "POST",
            "--url",
            ajax_url,
        ]
        for key, value in payload.items():
            curl_command.extend(["--data-urlencode", f"{key}={value}"])

        completed = subprocess.run(
            curl_command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0 and "kutu-urun-border" in completed.stdout:
            return completed.stdout
        return None

    @staticmethod
    def _extract_ajax_params(html_text: str) -> Optional[Dict[str, str]]:
        token_match = re.search(r"secimi_daralt_urunler\.asp\?h=([A-Za-z0-9%:\. ]+)", html_text)
        category_match = re.search(r'FiltreSabitleri\s*=\s*\{\s*"Kategori"\s*:\s*(\d+)', html_text)
        if token_match is None or category_match is None:
            return None
        return {
            "token": token_match.group(1),
            "category_id": category_match.group(1),
        }

    @staticmethod
    def _category_name(category_path: str) -> str:
        slug = category_path.strip("/").split("/")[-1].split(".html", 1)[0]
        normalized = re.sub(r"^c-\d+-", "", slug)
        return normalized.replace("-", " ").title() or "Genel"

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        product_link = card.select_one("a.kutu-link[href]")
        price_container = card.select_one(".urun-fiyat")
        if product_link is None or price_container is None:
            return None

        href = product_link.get("href") or ""
        name = self._clean_text(product_link.get("title") or product_link.get_text(" ", strip=True))
        if not href or not name:
            return None

        current_price, old_price = self._parse_price_values(price_container.get_text(" ", strip=True))
        if current_price is None or current_price <= 0:
            return None

        product_id_match = re.search(r"p-(\d+)-", href)
        if product_id_match is None:
            return None

        image_tag = card.select_one("img[src]")
        image_url = None
        if image_tag is not None:
            image_path = image_tag.get("src")
            if image_path and not image_path.startswith("data:image"):
                image_url = urljoin(self.base_url, image_path)

        stock_text = self._clean_text((card.select_one(".urun-liste-buton") or card).get_text(" ", strip=True)) or ""
        payload = {
            "url": urljoin(self.base_url, href),
            "category": category_name,
        }
        promo_price = current_price if old_price and old_price > current_price else None
        listed_price = old_price if old_price and old_price > current_price else current_price

        return RawOffer(
            source_product_id=product_id_match.group(1),
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="out_of_stock" if "stokta yok" in stock_text.lower() else "in_stock",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )


class KalafatlarAdapter(KommerzCategoryAjaxAdapter):
    market_key = "kalafatlar_ordu"
    base_url = "https://kalafatlar.com"
    category_paths = (
        "/c-1557-meyve-sebze.html",
        "/c-1547-sut-ve-kahvaltilik.html",
        "/c-1535-temel-gida.html",
    )


class MarasMarketAdapter(TSoftCategoryAdapter):
    market_key = "maras_market_kahramanmaras"
    base_url = "https://marasmarket.com"
    category_paths = (
        "/maras-yoresel-tatlari",
        "/bakliyat",
        "/biber-119",
    )


class KDepoAdapter(PrestaShopElementorCatalogAdapter):
    market_key = "k_depo_manisa"
    base_url = "https://k-depo.com"
    category_paths = (
        "/toz-urunler",
        "/icecek",
        "/temizlik",
    )


class SaladdoAdapter(WixStoresCategoryAdapter):
    market_key = "saladdo_antalya"
    base_url = "https://www.saladdo.com"
    fallback_category_paths = (
        "/vegetables",
        "/meyveler",
        "/",
    )

    def __init__(self, max_products: int = 10000, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(max_products=max_products, request_timeout=request_timeout, max_retries=max_retries)

    def _discover_category_paths(self) -> Tuple[str, ...]:
        response = self._safe_get(self.base_url)
        if response is None:
            return self.fallback_category_paths
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        discovered_paths: List[str] = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href") or ""
            parsed = urlparse(urljoin(self.base_url, href))
            if parsed.netloc not in {"www.saladdo.com", "saladdo.com"}:
                continue
            path = parsed.path.rstrip("/") or "/"
            if path == "/":
                continue
            segments = [segment for segment in path.split("/") if segment]
            if len(segments) != 1:
                continue
            if any(token in path for token in ("product-page", "cart", "checkout", "account")):
                continue
            if path not in discovered_paths:
                discovered_paths.append(path)
            if len(discovered_paths) >= 30:
                break
        return tuple(discovered_paths) if discovered_paths else self.fallback_category_paths


class ShowmarAdapter(ShowcaseCategoryAdapter):
    market_key = "showmar_istanbul"
    base_url = "https://www.showmar.com.tr"
    fallback_category_paths = (
        "/kategori/meyve-sebze",
        "/kategori/sut-kahvaltilik",
        "/kategori/yemeklik-malzemeler",
        "/kategori/biskuvi-cikolata-kuruyemis",
        "/kategori/deterjan-temizlik",
        "/kategori/bebek-urunleri",
        "/kategori/elektronik",
    )

    def __init__(self, max_products: int = 10000, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(max_products=max_products, request_timeout=request_timeout, max_retries=max_retries)

    def _discover_category_paths(self) -> Tuple[str, ...]:
        response = self._safe_get(self.base_url)
        if response is None:
            return self.fallback_category_paths
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        discovered_paths: List[str] = []
        for anchor in soup.select("a[href]"):
            href = anchor.get("href") or ""
            if href.startswith("/https://") or href.startswith("/http://"):
                continue
            parsed = urlparse(urljoin(self.base_url, href))
            path = parsed.path.rstrip("/")
            if not path.startswith("/kategori/"):
                continue
            if path not in discovered_paths:
                discovered_paths.append(path)
            if len(discovered_paths) >= 200:
                break
        return tuple(discovered_paths) if discovered_paths else self.fallback_category_paths

    def _fetch_html(self, category_path: str) -> Optional[str]:
        best_html: Optional[str] = None
        seen_signatures = set()
        for page in range(1, 21):
            url = urljoin(self.base_url, category_path)
            if page > 1:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}tp={page}"
            html_text = None
            for attempt in range(self.max_retries + 3):
                response = self._safe_get(url)
                if response is None:
                    continue
                if response.status_code == 429:
                    time.sleep(min(4.0, 1.0 + attempt))
                    continue
                if response.status_code in {404, 410}:
                    response = None
                    break
                response.raise_for_status()
                html_text = response.text
                break
            if not html_text:
                break
            if ".showcase-title" not in html_text and "data-product-id" not in html_text:
                break
            signature = tuple(re.findall(r'data-product-id="(\d+)"', html_text))
            if signature in seen_signatures:
                break
            seen_signatures.add(signature)
            count = len(signature)
            if count > 0:
                best_html = f"{best_html or ''}\n{html_text}" if best_html else html_text
            if count <= 0:
                break
        return best_html


class GroseriCatalogAdapter(HtmlStorefrontAdapter):
    market_key = "groseri_catalog"
    base_url = "https://www.groseri.com.tr"
    fallback_category_paths: Tuple[str, ...] = (
        "/kategoriler/100/salca-bulyon-harclar",
        "/kategoriler/283/icecekler",
        "/kategoriler/329/camasir-yikama",
        "/kategoriler/225/et-sarkuteri",
    )

    def __init__(self, max_products: int = 10000, max_categories: int = 400, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products
        self.max_categories = max_categories

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_path in self._discover_category_paths():
            page = 1
            empty_or_repeat_pages = 0
            while empty_or_repeat_pages < 2:
                response = self._safe_get(self._category_page_url(category_path, page))
                if response is None:
                    empty_or_repeat_pages += 1
                    page += 1
                    continue
                if response.status_code in {404, 410}:
                    break
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.select("div.thumbnail")
                if not cards:
                    empty_or_repeat_pages += 1
                    page += 1
                    continue
                category_name = self._category_name(category_path)
                before_count = len(offers)
                for card in cards:
                    offer = self._parse_card(card, category_name)
                    if offer is None or offer.source_product_id in seen_ids:
                        continue
                    seen_ids.add(offer.source_product_id)
                    offers.append(offer)
                    if len(offers) >= self.max_products:
                        return offers
                if len(offers) == before_count:
                    empty_or_repeat_pages += 1
                else:
                    empty_or_repeat_pages = 0
                page += 1
        return offers

    def _discover_category_paths(self) -> Tuple[str, ...]:
        response = self._safe_get(self.base_url)
        if response is None:
            return self.fallback_category_paths

        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        discovered_paths: List[str] = []
        for anchor in soup.select("a[href^='/kategoriler/']"):
            href = anchor.get("href") or ""
            parsed = urlparse(urljoin(self.base_url, href))
            path = parsed.path.rstrip("/")
            if not path.startswith("/kategoriler/"):
                continue
            if path not in discovered_paths:
                discovered_paths.append(path)
            if len(discovered_paths) >= self.max_categories:
                break
        if not discovered_paths:
            return self.fallback_category_paths
        return tuple(discovered_paths)

    @staticmethod
    def _category_name(category_path: str) -> str:
        slug = category_path.strip("/").split("/")[-1] or "genel"
        return slug.replace("-", " ").title()

    def _category_page_url(self, category_path: str, page: int) -> str:
        url = urljoin(self.base_url, category_path)
        if page <= 1:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}page={page}"

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        detail_link = card.select_one(".caption a[href]") or card.select_one(".product > a[href]")
        current_price_tag = card.select_one(".caption .fiyat")
        if detail_link is None or current_price_tag is None:
            return None

        name = self._clean_text(detail_link.get_text(" ", strip=True))
        current_price = self._parse_price(current_price_tag.get_text(" ", strip=True))
        if not name or current_price is None or current_price <= 0:
            return None

        old_price_tag = card.select_one(".caption .eski-fiyat")
        old_price = self._parse_price(old_price_tag.get_text(" ", strip=True)) if old_price_tag is not None else None
        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None

        source_product_id = self._product_id(card, detail_link)
        image_url = None
        image_tag = card.select_one(".product img")
        if image_tag is not None:
            image_path = image_tag.get("src") or image_tag.get("data-src")
            if image_path:
                image_url = urljoin(self.base_url, image_path)

        quick_view_link = card.select_one("a.gozat[href]")
        unit_label = None
        unit_tag = card.select_one(".birim")
        if unit_tag is not None:
            unit_label = self._clean_text(unit_tag.get_text(" ", strip=True))

        payload = {
            "url": urljoin(self.base_url, detail_link.get("href") or ""),
            "quick_view_url": urljoin(self.base_url, quick_view_link.get("href") or "") if quick_view_link is not None else None,
            "category": category_name,
        }

        return RawOffer(
            source_product_id=source_product_id,
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=unit_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    @staticmethod
    def _product_id(card: Tag, detail_link: Tag) -> str:
        hidden_input = card.select_one("input[name='urunId'][value]")
        if hidden_input is not None:
            product_id = (hidden_input.get("value") or "").strip()
            if product_id:
                return product_id
        href = detail_link.get("href") or ""
        return href.strip("/").split("/")[-1]


class TasoMarketAdapter(SitemapProductDetailAdapter):
    market_key = "taso_market_kocaeli"
    base_url = "https://www.tasomarket.com"


class GroseriAdanaAdapter(GroseriCatalogAdapter):
    market_key = "groseri_adana"


class GroseriMersinAdapter(GroseriCatalogAdapter):
    market_key = "groseri_mersin"


class IzmarAdapter(HtmlStorefrontAdapter):
    market_key = "izmar_izmir"
    base_url = "https://www.izmar.info"

    def __init__(self, max_products: int = 5000, max_pages: int = 250, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products
        self.max_pages = max_pages

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for page in range(1, self.max_pages + 1):
            html_text = self._fetch_page_html(page)
            if not html_text:
                continue
            soup = BeautifulSoup(html_text, "html.parser")
            cards = soup.select(".price_opacity_area .price__box")
            if not cards:
                break
            for index, card in enumerate(cards, start=1):
                offer = self._parse_card(card, page, index)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _fetch_page_html(self, page: int) -> Optional[str]:
        url = f"{self.base_url}/products"
        if page > 1:
            url = f"{url}?{urlencode({'page': page})}"
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
                    url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and "price__box" in completed.stdout:
                return completed.stdout
        return None

    def _parse_card(self, card: Tag, page: int, index: int) -> Optional[RawOffer]:
        category_tag = card.select_one(".price_box_header span")
        name_tag = card.select_one(".price_box_middle h4")
        price_tag = card.select_one(".price_box_footer h2")
        unit_tag = card.select_one(".price_box_footer h5")
        if category_tag is None or name_tag is None or price_tag is None:
            return None

        category_name = self._clean_text(category_tag.get_text(" ", strip=True))
        name = self._clean_text(name_tag.get_text(" ", strip=True))
        if not category_name or not name:
            return None

        listed_price = self._parse_izmar_price(price_tag.get_text(" ", strip=True))
        if listed_price is None or listed_price <= 0:
            return None

        unit_label = self._clean_text(unit_tag.get_text(" ", strip=True)) if unit_tag is not None else None
        product_id = f"{category_name.lower()}::{'-'.join(name.lower().split())}::{unit_label or 'ad'}"

        return RawOffer(
            source_product_id=product_id,
            source_category=category_name,
            source_name=name,
            source_brand="IZMAR" if name.startswith("IZMAR") or name.startswith("İZMAR") else None,
            source_size=unit_label,
            listed_price=listed_price,
            promo_price=None,
            stock_status="unknown",
            image_url=None,
            payload_json=json.dumps(
                {
                    "page": page,
                    "position": index,
                    "category": category_name,
                    "unit_label": unit_label,
                    "url": f"{self.base_url}/products?page={page}",
                },
                ensure_ascii=True,
            ),
        )

    @staticmethod
    def _parse_izmar_price(text: str) -> Optional[float]:
        normalized = re.sub(r"[^0-9,.\-]", "", text)
        if not normalized:
            return None
        if "," in normalized and "." in normalized:
            if normalized.rfind(".") > normalized.rfind(","):
                normalized = normalized.replace(",", "")
            else:
                normalized = normalized.replace(".", "").replace(",", ".")
        elif "," in normalized:
            parts = normalized.split(",")
            if len(parts[-1]) == 3:
                normalized = "".join(parts)
            else:
                normalized = normalized.replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return None


class NextJsCardCatalogAdapter(HtmlStorefrontAdapter):
    market_key = "nextjs_card_catalog"
    category_paths: Tuple[str, ...] = ("/",)

    def __init__(self, max_products: int = 5000, request_timeout: int = 20, max_retries: int = 1):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids = set()
        for category_path in self.category_paths:
            html_text = self._fetch_html(category_path)
            if not html_text:
                continue
            soup = BeautifulSoup(html_text, "html.parser")
            category_name = self._category_name(soup, category_path)
            for card in self._product_cards(soup):
                offer = self._parse_card(card, category_name)
                if offer is None or offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _fetch_html(self, category_path: str) -> Optional[str]:
        url = urljoin(self.base_url, category_path)
        response = self._safe_get(url)
        if response is not None and "page_product_name__" in response.text:
            return response.text
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
                    url,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and "page_product_name__" in completed.stdout:
                return completed.stdout
        return None

    def _product_cards(self, soup: BeautifulSoup) -> List[Tag]:
        cards: List[Tag] = []
        seen_ids = set()
        for anchor in soup.select("a[href*='-p-']"):
            href = anchor.get("href") or ""
            product_id = self._product_id_from_href(href)
            if product_id is None or product_id in seen_ids:
                continue
            card = self._find_product_card(anchor)
            if card is None:
                continue
            seen_ids.add(product_id)
            cards.append(card)
        return cards

    def _find_product_card(self, node: Tag) -> Optional[Tag]:
        current: Optional[Tag] = node
        while current is not None:
            if self._has_class_prefix(current, "page_product__"):
                return current
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
        return None

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        product_link = card.select_one("a[href*='-p-']")
        name_tag = self._first_descendant_with_class_prefix(card, "page_product_name__")
        current_price_tag = self._first_descendant_with_class_prefix(card, "page_product_price__")
        if product_link is None or name_tag is None or current_price_tag is None:
            return None

        href = product_link.get("href") or ""
        product_id = self._product_id_from_href(href)
        if product_id is None:
            return None

        name = self._clean_text(name_tag.get_text(" ", strip=True))
        current_price = self._parse_price(current_price_tag.get_text(" ", strip=True))
        if not name or current_price is None or current_price <= 0:
            return None

        old_price_tag = self._first_descendant_with_class_prefix(card, "page_product_price_old__")
        old_price = self._parse_price(old_price_tag.get_text(" ", strip=True)) if old_price_tag is not None else None
        listed_price = old_price if old_price and old_price > current_price else current_price
        promo_price = current_price if old_price and old_price > current_price else None

        unit_label = None
        unit_tag = self._first_descendant_with_class_prefix(card, "page_unitLabelText__")
        if unit_tag is not None:
            unit_label = self._clean_text(unit_tag.get_text(" ", strip=True))
            if unit_label:
                unit_label = unit_label.strip("() ")

        image_tag = card.select_one("img[src]")
        image_url = None
        if image_tag is not None and image_tag.get("src"):
            image_url = urljoin(self.base_url, image_tag.get("src"))

        payload = {
            "url": urljoin(self.base_url, href),
            "category_path": category_name,
        }

        return RawOffer(
            source_product_id=product_id,
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=unit_label,
            listed_price=listed_price,
            promo_price=promo_price,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )

    def _category_name(self, soup: BeautifulSoup, category_path: str) -> str:
        heading = soup.select_one("h1")
        if heading is not None:
            name = self._clean_text(heading.get_text(" ", strip=True))
            if name:
                return name
        if category_path == "/":
            return "Genel"
        slug = category_path.strip("/").split("/")[-1] or "genel"
        return slug.replace("-", " ").title()

    @staticmethod
    def _product_id_from_href(href: str) -> Optional[str]:
        match = re.search(r"-p-(\d+)", href)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _has_class_prefix(tag: Tag, prefix: str) -> bool:
        return any(class_name.startswith(prefix) for class_name in (tag.get("class") or []))

    @staticmethod
    def _first_descendant_with_class_prefix(tag: Tag, prefix: str) -> Optional[Tag]:
        return tag.find(
            lambda node: isinstance(node, Tag)
            and any(class_name.startswith(prefix) for class_name in (node.get("class") or []))
        )


class ErenlerAdapter(OpenCartSearchAdapter):
    market_key = "erenler_tokat"
    base_url = "https://www.erenlercep.com"


class SozSanalMarketAdapter(OpenCartSearchAdapter):
    market_key = "soz_sanal_market_afyon"
    base_url = "https://www.afyonsoz.com"


class IyasAdapter(NextJsCardCatalogAdapter):
    market_key = "iyas_isparta"
    base_url = "https://www.iyas.com.tr"


class SehzadeStoreAdapter(NextJsCardCatalogAdapter):
    market_key = "sehzade_kayseri"
    base_url = "https://sehzadeonline.com"
