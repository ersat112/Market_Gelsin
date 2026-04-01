from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class FetchContext:
    market_key: str
    city_name: str
    city_plate_code: int
    address_label: Optional[str] = None
    district: Optional[str] = None
    neighborhood: Optional[str] = None


@dataclass(frozen=True)
class RawOffer:
    source_product_id: Optional[str]
    source_category: str
    source_name: str
    source_brand: Optional[str]
    source_size: Optional[str]
    listed_price: float
    promo_price: Optional[float]
    stock_status: str
    image_url: Optional[str]
    payload_json: Optional[str] = None
    source_barcode: Optional[str] = None


class MarketAdapter(ABC):
    market_key: str

    @abstractmethod
    def fetch_offers(self, context: FetchContext) -> List[RawOffer]:
        raise NotImplementedError
