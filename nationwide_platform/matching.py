from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set

from .normalization import NormalizedProduct, normalize_barcode, normalize_product_name, tokenize


@dataclass(frozen=True)
class MatchResult:
    query: str
    candidate: str
    score: float
    strategy: str = "name"


def _jaccard(left: Set[str], right: Set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = left & right
    union = left | right
    return len(intersection) / len(union)


def score_product_match(query: str, candidate: str) -> float:
    query_product = normalize_product_name(query)
    candidate_product = normalize_product_name(candidate)

    query_tokens = set(tokenize(query_product.normalized_name))
    candidate_tokens = set(tokenize(candidate_product.normalized_name))

    score = _jaccard(query_tokens, candidate_tokens)

    if query_product.size_value and candidate_product.size_value:
        if query_product.size_unit == candidate_product.size_unit:
            size_delta = abs(query_product.size_value - candidate_product.size_value)
            if size_delta == 0:
                score += 0.25
            elif size_delta <= max(1, query_product.size_value * 0.1):
                score += 0.1

    if query_product.normalized_name in candidate_product.normalized_name:
        score += 0.15

    return round(min(score, 1.0), 4)


def score_barcode_match(query_barcode: Optional[str], candidate_barcode: Optional[str]) -> float:
    left = normalize_barcode(query_barcode)
    right = normalize_barcode(candidate_barcode)
    if left is None or right is None:
        return 0.0
    if left == right:
        return 1.0
    return 0.0


def score_offer_match(
    query: str,
    candidate: str,
    query_barcode: Optional[str] = None,
    candidate_barcode: Optional[str] = None,
) -> MatchResult:
    barcode_score = score_barcode_match(query_barcode, candidate_barcode)
    if barcode_score == 1.0:
        return MatchResult(query=query, candidate=candidate, score=1.0, strategy="barcode")
    return MatchResult(query=query, candidate=candidate, score=score_product_match(query, candidate), strategy="name")


def rank_candidates(query: str, candidates: Sequence[str], min_score: float = 0.25) -> List[MatchResult]:
    matches = [
        MatchResult(query=query, candidate=candidate, score=score_product_match(query, candidate), strategy="name")
        for candidate in candidates
    ]
    return [match for match in sorted(matches, key=lambda item: item.score, reverse=True) if match.score >= min_score]


def best_candidate(query: str, candidates: Iterable[str], min_score: float = 0.25) -> Optional[MatchResult]:
    ranked = rank_candidates(query, list(candidates), min_score=min_score)
    return ranked[0] if ranked else None
