import json
import re
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .base import FetchContext, RawOffer
from .custom_html import HtmlStorefrontAdapter


class BimAktuelAdapter(HtmlStorefrontAdapter):
    market_key = "bim_market"
    base_url = "https://www.bim.com.tr"
    listing_path = "/Categories/100/aktuel-urunler.aspx"

    def __init__(
        self,
        max_products: int = 250,
        max_campaign_pages: int = 12,
        request_timeout: int = 20,
        max_retries: int = 1,
    ):
        super().__init__(request_timeout=request_timeout, max_retries=max_retries)
        self.max_products = max_products
        self.max_campaign_pages = max_campaign_pages

    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        landing_response = self._safe_get(urljoin(self.base_url, self.listing_path))
        if landing_response is None:
            return []
        landing_response.raise_for_status()

        campaign_labels = self._campaign_labels(landing_response.text)
        if not campaign_labels:
            return self._parse_listing_page(landing_response.text, campaign_label="Aktuel Urunler")

        offers: List[RawOffer] = []
        seen_ids = set()
        for campaign_key, campaign_label in list(campaign_labels.items())[: self.max_campaign_pages]:
            campaign_url = urljoin(self.base_url, f"{self.listing_path}?top=1&Bim_AktuelTarihKey={campaign_key}")
            response = self._safe_get(campaign_url)
            if response is None:
                continue
            response.raise_for_status()
            page_offers = self._parse_listing_page(response.text, campaign_label=campaign_label)
            for offer in page_offers:
                if offer.source_product_id in seen_ids:
                    continue
                seen_ids.add(offer.source_product_id)
                offers.append(offer)
                if len(offers) >= self.max_products:
                    return offers
        return offers

    def _parse_listing_page(self, html_text: str, campaign_label: str) -> List[RawOffer]:
        soup = BeautifulSoup(html_text, "html.parser")
        offers: List[RawOffer] = []
        for card in soup.select(".product"):
            offer = self._parse_card(card, campaign_label)
            if offer is not None:
                offers.append(offer)
        return offers

    def _parse_card(self, card: Tag, campaign_label: str) -> Optional[RawOffer]:
        product_link = card.select_one("a[href*='/aktuel-urunler/']")
        title_tag = card.select_one("h2.title")
        price_tag = card.select_one(".buttonArea a.gButton")
        if product_link is None or title_tag is None or price_tag is None:
            return None

        href = (product_link.get("href") or "").strip()
        name = self._clean_text(title_tag.get_text(" ", strip=True))
        price = self._parse_bim_price(price_tag)
        if not href or not name or price is None or price <= 0:
            return None

        source_product_id = self._product_id(card, href)
        if source_product_id is None:
            return None

        image_tag = card.select_one("img")
        image_url = None
        if image_tag is not None:
            image_path = image_tag.get("src") or image_tag.get("data-src")
            if image_path and not image_path.startswith("data:image"):
                image_url = urljoin(self.base_url, image_path)

        features = []
        for item in card.select(".textArea li .text"):
            text = self._clean_text(item.get_text(" ", strip=True))
            if text:
                features.append(text)

        payload = {
            "url": urljoin(self.base_url, href),
            "campaign": campaign_label,
            "features": features,
        }

        return RawOffer(
            source_product_id=source_product_id,
            source_category=campaign_label,
            source_name=name,
            source_brand=None,
            source_size=None,
            listed_price=price,
            promo_price=None,
            stock_status="unknown",
            image_url=image_url,
            payload_json=json.dumps(payload, ensure_ascii=True),
            source_barcode=None,
        )

    @staticmethod
    def _campaign_labels(html_text: str) -> Dict[str, str]:
        soup = BeautifulSoup(html_text, "html.parser")
        labels: Dict[str, str] = {}
        for anchor in soup.select("a[href*='Bim_AktuelTarihKey=']"):
            href = anchor.get("href") or ""
            campaign_key = parse_qs(urlparse(href).query).get("Bim_AktuelTarihKey", [None])[0]
            label = HtmlStorefrontAdapter._clean_text(anchor.get_text(" ", strip=True))
            if campaign_key and label and campaign_key not in labels:
                labels[campaign_key] = label
        return labels

    @staticmethod
    def _product_id(card: Tag, href: str) -> Optional[str]:
        share_link = card.select_one(".shareArea a[data-id]")
        if share_link is not None:
            share_id = HtmlStorefrontAdapter._clean_text(share_link.get("data-id"))
            if share_id:
                return share_id
        slug = urlparse(href).path.strip("/").split("/")[-2:-1]
        if slug:
            return slug[0]
        return None

    @staticmethod
    def _parse_bim_price(price_tag: Tag) -> Optional[float]:
        whole_tag = price_tag.select_one(".text.quantify")
        decimal_tag = price_tag.select_one(".kusurArea .number")
        if whole_tag is not None:
            whole_digits = re.sub(r"[^\d]", "", whole_tag.get_text(" ", strip=True))
            decimal_digits = "00"
            if decimal_tag is not None:
                clean_decimal = re.sub(r"[^\d]", "", decimal_tag.get_text(" ", strip=True))
                if clean_decimal:
                    decimal_digits = clean_decimal[-2:].zfill(2)
            if whole_digits:
                try:
                    return float(f"{int(whole_digits)}.{decimal_digits}")
                except ValueError:
                    return None
        text = " ".join(price_tag.get_text(" ", strip=True).split())
        match = re.search(r"([\d.]+)\s*,\s*(\d{2})", text)
        if match:
            whole_digits = match.group(1).replace(".", "")
            decimal_digits = match.group(2)
            try:
                return float(f"{int(whole_digits)}.{decimal_digits}")
            except ValueError:
                return None
        return None
