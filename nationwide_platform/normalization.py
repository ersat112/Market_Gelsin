import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


SIZE_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|gr|lt|l|ml|cl|adet|li|lu|paket|pk)",
    re.IGNORECASE,
)

BRAND_SPLIT_PATTERN = re.compile(r"\s+")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9\s]")
BARCODE_PATTERN = re.compile(r"\b(?:\d{8}|\d{12,14})\b")


@dataclass(frozen=True)
class NormalizedProduct:
    original_name: str
    normalized_name: str
    size_value: Optional[float]
    size_unit: Optional[str]
    fingerprint: str


def normalize_text(value: str) -> str:
    value = value.lower()
    value = value.replace("ç", "c").replace("ğ", "g").replace("ı", "i").replace("ö", "o").replace("ş", "s").replace("ü", "u")
    value = NON_ALNUM_PATTERN.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def extract_size(value: str) -> Tuple[Optional[float], Optional[str]]:
    match = SIZE_PATTERN.search(value)
    if not match:
        return None, None

    size_value = float(match.group("value").replace(",", "."))
    size_unit = match.group("unit").lower()
    return size_value, size_unit


def normalize_product_name(name: str) -> NormalizedProduct:
    normalized_name = normalize_text(name)
    size_value, size_unit = extract_size(normalized_name)
    fingerprint = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:16]
    return NormalizedProduct(
        original_name=name,
        normalized_name=normalized_name,
        size_value=size_value,
        size_unit=size_unit,
        fingerprint=fingerprint,
    )


def tokenize(value: str) -> List[str]:
    return [token for token in BRAND_SPLIT_PATTERN.split(normalize_text(value)) if token]


def normalize_barcode(value: Optional[str], strict: bool = False) -> Optional[str]:
    if value is None:
        return None
    compact = re.sub(r"[\s-]", "", str(value))
    if strict:
        if not re.fullmatch(r"(?:\d{8}|\d{12,14})", compact):
            return None
        digits = compact
    else:
        digits = re.sub(r"\D", "", compact)
    if len(digits) not in {8, 12, 13, 14}:
        return None
    if strict and not has_valid_gtin_checksum(digits):
        return None
    return digits


def extract_barcode_candidates(value: Optional[str], strict: bool = True) -> List[str]:
    if not value:
        return []
    barcodes: List[str] = []
    for match in BARCODE_PATTERN.findall(str(value)):
        barcode = normalize_barcode(match, strict=strict)
        if barcode and barcode not in barcodes:
            barcodes.append(barcode)
    return barcodes


def has_valid_gtin_checksum(digits: str) -> bool:
    payload = digits[:-1]
    checksum = int(digits[-1])
    weighted_sum = 0
    reversed_payload = list(reversed(payload))
    for index, char in enumerate(reversed_payload):
        multiplier = 3 if index % 2 == 0 else 1
        weighted_sum += int(char) * multiplier
    calculated = (10 - (weighted_sum % 10)) % 10
    return checksum == calculated
