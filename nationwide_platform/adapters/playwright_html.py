import json
import re
from typing import List, Optional, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .base import FetchContext, MarketAdapter, RawOffer


class YunusPlaywrightAdapter(MarketAdapter):
    market_key = "yunus_market_ankara"
    base_url = "https://www.yunusonline.com"
    seed_path = "/meyve-sebze-2"

    def __init__(self, max_products: int = 10000, max_categories: int = 120, wait_ms: int = 2500):
        self.max_products = max_products
        self.max_categories = max_categories
        self.wait_ms = wait_ms

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        offers: List[RawOffer] = []
        seen_ids: Set[str] = set()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                seed_html = self._load_html(page, self.seed_path)
                if not seed_html:
                    return offers

                category_paths = self._category_paths(seed_html)
                for category_path in category_paths[: self.max_categories]:
                    html_text = self._load_html(page, category_path)
                    if not html_text:
                        continue
                    soup = BeautifulSoup(html_text, "html.parser")
                    category_name = self._category_name(soup, category_path)
                    for card in soup.select(".product-cart-wrap"):
                        offer = self._parse_card(card, category_name)
                        if offer is None or offer.source_product_id in seen_ids:
                            continue
                        seen_ids.add(offer.source_product_id)
                        offers.append(offer)
                        if len(offers) >= self.max_products:
                            return offers
                return offers
            finally:
                browser.close()

    def _load_html(self, page, path: str) -> Optional[str]:
        url = urljoin(self.base_url, path)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(self.wait_ms)
            return page.content()
        except PlaywrightTimeoutError:
            return None
        except Exception:
            return None

    def _category_paths(self, html_text: str) -> List[str]:
        soup = BeautifulSoup(html_text, "html.parser")
        paths: List[str] = [self.seed_path]
        seen = {self.seed_path}
        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            normalized = self._normalize_category_path(href)
            if normalized is None or normalized in seen:
                continue
            seen.add(normalized)
            paths.append(normalized)
        return paths

    @staticmethod
    def _normalize_category_path(href: str) -> Optional[str]:
        if not href or href.startswith(("http://", "https://", "mailto:", "tel:", "#", "javascript:")):
            return None
        cleaned = href if href.startswith("/") else f"/{href}"
        if cleaned in {"/", "/gsm-account", "/search-query"}:
            return None
        if re.search(r"/[a-z0-9-]+-(?:t|s)-\d+$", cleaned, re.I):
            return cleaned
        return None

    @staticmethod
    def _category_name(soup: BeautifulSoup, category_path: str) -> str:
        title = soup.title.get_text(" ", strip=True) if soup.title is not None else ""
        if title and "Yunus Online" not in title:
            return title
        slug = category_path.strip("/").rsplit("-", 2)[0] if "-" in category_path else category_path.strip("/")
        return slug.replace("-", " ").strip().title() or "Genel"

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        cleaned = text.replace("₺", " ").replace("TL", " ").replace("tl", " ")
        match = re.search(r"(\d+(?:[.,]\d+)?)", cleaned)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None

    def _parse_card(self, card: Tag, category_name: str) -> Optional[RawOffer]:
        product_link = card.select_one("a[href*='-p-']")
        if product_link is None:
            return None

        href = product_link.get("href") or ""
        product_id_match = re.search(r"-p-(\d+)", href)
        if product_id_match is None:
            return None
        product_id = product_id_match.group(1)

        image_tag = card.select_one("img.default-img") or card.select_one("img[src]")
        image_url = urljoin(self.base_url, image_tag.get("src")) if image_tag and image_tag.get("src") else None

        name_tag = card.select_one(".product-content-wrap div a[style*='color:#737373']") or product_link
        name = " ".join(name_tag.get_text(" ", strip=True).split()) if name_tag is not None else None
        if not name and image_tag is not None:
            name = " ".join((image_tag.get("alt") or "").split())
        if not name:
            return None

        price_tag = card.select_one(".product-rate-cover span")
        if price_tag is None:
            return None
        listed_price = self._parse_price(price_tag.get_text(" ", strip=True))
        if listed_price is None or listed_price <= 0:
            return None

        badge_tag = card.select_one(".product-badges a")
        badge_label = " ".join(badge_tag.get_text(" ", strip=True).split()) if badge_tag is not None else None
        payload = {
            "url": urljoin(self.base_url, href),
            "badge": badge_label,
            "category": category_name,
        }

        return RawOffer(
            source_product_id=product_id,
            source_category=category_name,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=listed_price,
            promo_price=None,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
        )
