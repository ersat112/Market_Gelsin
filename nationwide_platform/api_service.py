import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from statistics import median
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from .collection_program import HOT_PRODUCT_REFRESH_HOURS, WEEKLY_FULL_REFRESH_HOURS
from .matching import score_offer_match
from .normalization import normalize_barcode
from .runtime_db import connect_runtime as connect


LATEST_OFFERS_CTE = """
SELECT *
FROM current_offers
"""

NATIONAL_COVERAGE_SCOPES = {
    "national_store_network",
    "wide_national",
    "all_81_target",
}

SOURCE_URL_KEYS = {
    "url",
    "link",
    "href",
    "permalink",
    "producturl",
    "product_url",
    "sourceurl",
    "source_url",
    "canonicalurl",
    "canonical_url",
    "deeplink",
    "detailurl",
    "detail_url",
}


def _row_dicts(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _active_price(row: Dict[str, Any]) -> float:
    promo_price = row.get("promo_price")
    return float(promo_price if promo_price is not None else row["listed_price"])


def _as_offer_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "market_key": row["market_key"],
        "city_slug": row["city_slug"],
        "display_name": row["display_name"],
        "listed_price": row["listed_price"],
        "promo_price": row.get("promo_price"),
        "active_price": _active_price(row),
        "availability": row.get("availability"),
        "barcode": row.get("source_barcode"),
        "unit_label": row.get("unit_label"),
        "image_url": row.get("image_url"),
        "observed_at": row.get("observed_at"),
    }


def get_platform_status() -> Dict[str, Any]:
    with connect() as connection:
        cursor = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM cities) AS city_count,
                (SELECT COUNT(*) FROM source_markets WHERE is_active = 1) AS active_market_count,
                (SELECT COUNT(*) FROM market_city_targets) AS city_target_count,
                (SELECT COUNT(*) FROM city_local_coverage_status WHERE coverage_status = 'verified_local_sources') AS verified_city_count,
                (SELECT COUNT(*) FROM local_market_candidates) AS local_candidate_count,
                (SELECT COUNT(*) FROM scrape_runs) AS scrape_run_count,
                (SELECT COUNT(*) FROM offers) AS offer_count,
                (SELECT COUNT(*) FROM current_offers) AS current_offer_count,
                (SELECT COUNT(*) FROM canonical_products) AS canonical_product_count,
                (SELECT COUNT(*) FROM canonical_product_barcodes) AS barcode_count,
                (SELECT COUNT(*) FROM market_adapter_readiness WHERE adapter_status = 'live') AS live_adapter_count,
                (SELECT COUNT(*) FROM market_adapter_readiness WHERE adapter_status <> 'live') AS planned_adapter_count,
                (SELECT COUNT(*) FROM city_collection_program WHERE municipality_tier = 'metropolitan_municipality') AS metro_city_count,
                (SELECT COUNT(*) FROM city_collection_program WHERE local_launch_wave = 'v1_metro_local') AS v1_city_count,
                (SELECT COUNT(*) FROM city_collection_program WHERE local_launch_wave = 'v2_remaining_local') AS v2_city_count,
                (SELECT COUNT(*) FROM market_refresh_policy WHERE program_scope = 'v1_national_core') AS national_core_market_count,
                (SELECT COUNT(*) FROM barcode_scan_signals) AS scan_signal_count,
                (SELECT COUNT(*) FROM hot_product_refresh_candidates WHERE status = 'planned') AS planned_hot_refresh_count
            """
        )
        row = cursor.fetchone()
        return {
            "cities": row[0],
            "active_markets": row[1],
            "city_targets": row[2],
            "verified_cities": row[3],
            "local_candidates": row[4],
            "scrape_runs": row[5],
            "offers": row[6],
            "current_offers": row[7],
            "canonical_products": row[8],
            "barcodes": row[9],
            "live_adapters": row[10],
            "planned_adapters": row[11],
            "metro_cities": row[12],
            "v1_local_program_cities": row[13],
            "v2_local_program_cities": row[14],
            "v1_national_core_markets": row[15],
            "scan_signals": row[16],
            "planned_hot_refresh_candidates": row[17],
            "full_refresh_hours": WEEKLY_FULL_REFRESH_HOURS,
            "hot_refresh_hours": HOT_PRODUCT_REFRESH_HOURS,
        }


def get_collection_program_status() -> Dict[str, Any]:
    with connect() as connection:
        national_cursor = connection.execute(
            """
            SELECT sm.market_key, sm.name
            FROM market_refresh_policy mrp
            JOIN source_markets sm ON sm.market_key = mrp.market_key
            WHERE mrp.program_scope = 'v1_national_core'
            ORDER BY sm.name
            """
        )
        metro_cursor = connection.execute(
            """
            SELECT c.plate_code, c.name, c.slug, flow.rollout_stage, flow.live_market_count
            FROM city_collection_program program
            JOIN cities c ON c.plate_code = program.city_plate_code
            LEFT JOIN city_controlled_flow_plan flow ON flow.city_plate_code = c.plate_code
            WHERE program.local_launch_wave = 'v1_metro_local'
            ORDER BY c.plate_code
            """
        )
        remaining_cursor = connection.execute(
            """
            SELECT c.plate_code, c.name, c.slug, flow.rollout_stage, flow.live_market_count
            FROM city_collection_program program
            JOIN cities c ON c.plate_code = program.city_plate_code
            LEFT JOIN city_controlled_flow_plan flow ON flow.city_plate_code = c.plate_code
            WHERE program.local_launch_wave = 'v2_remaining_local'
            ORDER BY c.plate_code
            """
        )
        telemetry_cursor = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM barcode_scan_signals) AS scan_signal_count,
                (SELECT COUNT(*) FROM hot_product_refresh_candidates WHERE status = 'planned') AS planned_hot_refresh_count,
                (SELECT COUNT(*) FROM hot_product_refresh_candidates WHERE status = 'completed') AS completed_hot_refresh_count
            """
        )
        telemetry = telemetry_cursor.fetchone()
        national_markets = [
            {"market_key": row[0], "market_name": row[1]}
            for row in national_cursor.fetchall()
        ]
        metro_cities = [
            {
                "city_code": str(int(row[0])).zfill(2),
                "city_name": row[1],
                "city_slug": row[2],
                "rollout_stage": row[3],
                "live_market_count": row[4] or 0,
            }
            for row in metro_cursor.fetchall()
        ]
        remaining_cities = [
            {
                "city_code": str(int(row[0])).zfill(2),
                "city_name": row[1],
                "city_slug": row[2],
                "rollout_stage": row[3],
                "live_market_count": row[4] or 0,
            }
            for row in remaining_cursor.fetchall()
        ]
        return {
            "refresh_policy": {
                "full_refresh_hours": WEEKLY_FULL_REFRESH_HOURS,
                "hot_refresh_hours": HOT_PRODUCT_REFRESH_HOURS,
                "history_mode": "append_only_offer_snapshots",
                "image_capture_policy": "required",
            },
            "v1": {
                "national_core_markets": national_markets,
                "metro_local_cities": metro_cities,
            },
            "v2": {
                "remaining_local_cities": remaining_cities,
            },
            "telemetry": {
                "scan_signal_count": telemetry[0],
                "planned_hot_refresh_count": telemetry[1],
                "completed_hot_refresh_count": telemetry[2],
            },
        }


def list_cities() -> List[Dict[str, Any]]:
    with connect() as connection:
        cursor = connection.execute(
            f"""
            WITH latest_offer_counts AS (
                SELECT city_plate_code, COUNT(*) AS offer_count
                FROM ({LATEST_OFFERS_CTE})
                GROUP BY city_plate_code
            )
            SELECT
                c.plate_code,
                c.name,
                c.slug,
                c.region,
                program.municipality_tier,
                program.local_launch_wave,
                program.coverage_goal,
                program.full_refresh_hours,
                program.hot_refresh_hours,
                coverage.coverage_status,
                coverage.verified_market_count,
                flow.rollout_stage,
                flow.collection_mode,
                flow.primary_market_key,
                flow.fallback_market_key,
                flow.live_market_count,
                COALESCE(offers.offer_count, 0) AS offer_count
            FROM cities c
            LEFT JOIN city_collection_program program
                ON program.city_plate_code = c.plate_code
            LEFT JOIN city_local_coverage_status coverage
                ON coverage.city_plate_code = c.plate_code
            LEFT JOIN city_controlled_flow_plan flow
                ON flow.city_plate_code = c.plate_code
            LEFT JOIN latest_offer_counts offers
                ON offers.city_plate_code = c.plate_code
            ORDER BY c.plate_code
            """
        )
        return _row_dicts(cursor)


def get_city_markets(city_slug: str) -> List[Dict[str, Any]]:
    with connect() as connection:
        cursor = connection.execute(
            f"""
            WITH target_offers AS (
                SELECT
                    city_plate_code,
                    market_key,
                    COUNT(*) AS offer_count,
                    MAX(observed_at) AS last_observed_at
                FROM ({LATEST_OFFERS_CTE})
                GROUP BY city_plate_code, market_key
            )
            SELECT
                sm.market_key,
                sm.name,
                sm.segment,
                sm.coverage_scope,
                sm.pricing_scope,
                sm.crawl_strategy,
                sm.entrypoint_url,
                policy.program_scope,
                policy.launch_wave,
                policy.full_refresh_hours,
                policy.hot_refresh_hours,
                policy.hot_refresh_enabled,
                policy.image_capture_policy,
                mt.priority_score,
                mt.probe_strategy,
                mt.status AS target_status,
                readiness.adapter_status,
                readiness.adapter_family,
                readiness.complexity_level,
                COALESCE(target_offers.offer_count, 0) AS offer_count,
                target_offers.last_observed_at
            FROM cities c
            JOIN market_city_targets mt
                ON mt.city_plate_code = c.plate_code
            JOIN source_markets sm
                ON sm.market_key = mt.market_key
            LEFT JOIN market_refresh_policy policy
                ON policy.market_key = sm.market_key
            LEFT JOIN market_adapter_readiness readiness
                ON readiness.market_key = sm.market_key
            LEFT JOIN target_offers
                ON target_offers.city_plate_code = c.plate_code
               AND target_offers.market_key = sm.market_key
            WHERE c.slug = ?
            ORDER BY
                CASE readiness.adapter_status WHEN 'live' THEN 0 ELSE 1 END,
                COALESCE(target_offers.offer_count, 0) DESC,
                mt.priority_score DESC,
                sm.market_key
            """,
            (city_slug,),
        )
        return _row_dicts(cursor)


def search_offers(
    city_slug: str,
    query: Optional[str] = None,
    market_key: Optional[str] = None,
    barcode: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    normalized_barcode = normalize_barcode(barcode) if barcode else None
    where_clauses = ["city.slug = ?"]
    params: List[Any] = [city_slug]
    if market_key:
        where_clauses.append("offers.market_key = ?")
        params.append(market_key)
    if normalized_barcode:
        where_clauses.append("offers.source_barcode = ?")
        params.append(normalized_barcode)
    if query:
        where_clauses.append("LOWER(offers.display_name) LIKE ?")
        params.append(f"%{query.lower()}%")
    params.append(max(1, min(limit, 200)))

    sql = f"""
        SELECT
            offers.market_key,
            city.slug AS city_slug,
            offers.display_name,
            offers.listed_price,
            offers.promo_price,
            offers.availability,
            offers.source_barcode,
            offers.unit_label,
            offers.image_url,
            offers.observed_at
        FROM ({LATEST_OFFERS_CTE}) offers
        JOIN cities city ON city.plate_code = offers.city_plate_code
        WHERE {' AND '.join(where_clauses)}
        ORDER BY COALESCE(offers.promo_price, offers.listed_price) ASC, offers.observed_at DESC
        LIMIT ?
    """
    with connect() as connection:
        cursor = connection.execute(sql, params)
        return [_as_offer_payload(row) for row in _row_dicts(cursor)]


def lookup_barcode(barcode: str) -> Dict[str, Any]:
    normalized_barcode = normalize_barcode(barcode)
    if normalized_barcode is None:
        raise ValueError("invalid_barcode")

    with connect() as connection:
        cursor = connection.execute(
            f"""
            SELECT
                offers.market_key,
                cities.slug AS city_slug,
                offers.display_name,
                offers.listed_price,
                offers.promo_price,
                offers.availability,
                offers.source_barcode,
                offers.unit_label,
                offers.image_url,
                offers.observed_at
            FROM ({LATEST_OFFERS_CTE}) offers
            JOIN cities ON cities.plate_code = offers.city_plate_code
            WHERE offers.source_barcode = ?
            ORDER BY COALESCE(offers.promo_price, offers.listed_price) ASC, offers.observed_at DESC
            """,
            (normalized_barcode,),
        )
        offers = [_as_offer_payload(row) for row in _row_dicts(cursor)]

    return {
        "barcode": normalized_barcode,
        "match_count": len(offers),
        "offers": offers,
    }


def compare_basket(city_slug: str, items: List[str], min_score: float = 0.35) -> Dict[str, Any]:
    cleaned_items = [item.strip() for item in items if item and item.strip()]
    if not cleaned_items:
        return {
            "city_slug": city_slug,
            "items": [],
            "single_market_options": [],
            "split_basket_total": None,
            "split_basket_items": [],
        }

    with connect() as connection:
        cursor = connection.execute(
            f"""
            SELECT
                offers.market_key,
                city.slug AS city_slug,
                offers.display_name,
                offers.listed_price,
                offers.promo_price,
                offers.availability,
                offers.source_barcode,
                offers.unit_label,
                offers.image_url,
                offers.observed_at
            FROM ({LATEST_OFFERS_CTE}) offers
            JOIN cities city ON city.plate_code = offers.city_plate_code
            WHERE city.slug = ?
            """,
            (city_slug,),
        )
        city_offers = _row_dicts(cursor)

    per_item_matches: List[Dict[str, Any]] = []
    market_totals: Dict[str, Dict[str, Any]] = {}
    split_basket_items: List[Dict[str, Any]] = []

    for item in cleaned_items:
        item_matches: List[Dict[str, Any]] = []
        for offer in city_offers:
            match = score_offer_match(
                query=item,
                candidate=offer["display_name"],
                candidate_barcode=offer.get("source_barcode"),
            )
            if match.score < min_score:
                continue
            entry = {
                **_as_offer_payload(offer),
                "score": match.score,
                "strategy": match.strategy,
            }
            item_matches.append(entry)

        item_matches.sort(key=lambda entry: (-entry["score"], entry["active_price"], entry["market_key"]))
        best_by_market: Dict[str, Dict[str, Any]] = {}
        for entry in item_matches:
            current = best_by_market.get(entry["market_key"])
            if current is None or (entry["score"], -entry["active_price"]) > (current["score"], -current["active_price"]):
                best_by_market[entry["market_key"]] = entry

        selected_market_matches = list(best_by_market.values())
        selected_market_matches.sort(key=lambda entry: (-entry["score"], entry["active_price"], entry["market_key"]))
        best_overall = min(selected_market_matches, key=lambda entry: (entry["active_price"], -entry["score"])) if selected_market_matches else None

        per_item_matches.append(
            {
                "query": item,
                "matches": selected_market_matches[:10],
            }
        )

        if best_overall is not None:
            split_basket_items.append(
                {
                    "query": item,
                    "chosen_market_key": best_overall["market_key"],
                    "chosen_offer": best_overall,
                }
            )

        for market_key, entry in best_by_market.items():
            market_totals.setdefault(
                market_key,
                {
                    "market_key": market_key,
                    "matched_item_count": 0,
                    "total_price": 0.0,
                    "items": [],
                },
            )
            market_totals[market_key]["matched_item_count"] += 1
            market_totals[market_key]["total_price"] += entry["active_price"]
            market_totals[market_key]["items"].append(
                {
                    "query": item,
                    "offer": entry,
                }
            )

    single_market_options = sorted(
        [
            option
            for option in market_totals.values()
            if option["matched_item_count"] == len(cleaned_items)
        ],
        key=lambda option: (option["total_price"], option["market_key"]),
    )

    split_total = round(sum(item["chosen_offer"]["active_price"] for item in split_basket_items), 2) if split_basket_items else None
    for option in single_market_options:
        option["total_price"] = round(option["total_price"], 2)

    return {
        "city_slug": city_slug,
        "items": per_item_matches,
        "single_market_options": single_market_options[:10],
        "split_basket_total": split_total,
        "split_basket_items": split_basket_items,
    }


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _normalize_city_code(city_code: Optional[str]) -> Optional[int]:
    if city_code is None or str(city_code).strip() == "":
        return None
    try:
        normalized = int(str(city_code).strip())
    except ValueError as exc:
        raise ValueError("invalid_city_code") from exc
    if normalized < 1 or normalized > 81:
        raise ValueError("invalid_city_code")
    return normalized


def _resolve_city(connection: sqlite3.Connection, city_code: Optional[str]) -> Optional[Dict[str, Any]]:
    plate_code = _normalize_city_code(city_code)
    if plate_code is None:
        return None
    cursor = connection.execute(
        "SELECT plate_code, name, slug FROM cities WHERE plate_code = ?",
        (plate_code,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("invalid_city_code")
    return {
        "plate_code": int(row[0]),
        "code": str(int(row[0])).zfill(2),
        "name": row[1],
        "slug": row[2],
    }


def _data_freshness(connection: sqlite3.Connection, city_plate_code: Optional[int] = None) -> Dict[str, Any]:
    where_clause = "WHERE sr.status IN ('completed', 'completed_with_errors')"
    params: List[Any] = []
    if city_plate_code is not None:
        where_clause += " AND sr.city_plate_code = ?"
        params.append(city_plate_code)

    cursor = connection.execute(
        f"""
        WITH latest_market_runs AS (
            SELECT
                sr.market_key,
                sr.city_plate_code,
                MAX(COALESCE(sr.finished_at, sr.started_at)) AS finished_at
            FROM scrape_runs sr
            {where_clause}
            GROUP BY sr.market_key, sr.city_plate_code
        )
        SELECT
            MIN(latest_market_runs.finished_at) AS oldest_latest_refresh,
            MAX(latest_market_runs.finished_at) AS newest_latest_refresh,
            MAX(
                CASE
                    WHEN mrp.program_scope = 'v1_national_core' THEN latest_market_runs.finished_at
                    ELSE NULL
                END
            ) AS last_national_refresh,
            MIN(COALESCE(mrp.full_refresh_hours, ?)) AS min_full_refresh_hours,
            MIN(COALESCE(mrp.hot_refresh_hours, ?)) AS min_hot_refresh_hours,
            MAX(COALESCE(mrp.history_mode, 'append_only_offer_snapshots')) AS history_mode
        FROM latest_market_runs
        LEFT JOIN market_refresh_policy mrp
            ON mrp.market_key = latest_market_runs.market_key
        """,
        [*params, WEEKLY_FULL_REFRESH_HOURS, HOT_PRODUCT_REFRESH_HOURS],
    )
    row = cursor.fetchone()
    last_full = row[2] or row[1]
    last_hot = row[1] or row[0]
    return {
        "mode": "weekly_full_plus_hot_scan",
        "last_full_refresh_at": last_full,
        "last_hot_refresh_at": last_hot,
        "full_refresh_hours": row[3] or WEEKLY_FULL_REFRESH_HOURS,
        "hot_refresh_hours": row[4] or HOT_PRODUCT_REFRESH_HOURS,
        "history_mode": row[5] or "append_only_offer_snapshots",
    }


def _response_meta(
    connection: sqlite3.Connection,
    city_plate_code: Optional[int] = None,
    warnings: Optional[List[str]] = None,
    partial: bool = False,
) -> Dict[str, Any]:
    warning_list = warnings or []
    return {
        "fetched_at": _utcnow_iso(),
        "request_id": uuid.uuid4().hex,
        "data_freshness": _data_freshness(connection, city_plate_code=city_plate_code),
        "partial": partial or bool(warning_list),
        "warnings": warning_list,
    }


def _active_price_value(listed_price: Optional[float], promo_price: Optional[float]) -> Optional[float]:
    if promo_price is not None:
        return float(promo_price)
    if listed_price is not None:
        return float(listed_price)
    return None


def _canonical_offer_source_subquery(offer_alias: str) -> str:
    return f"""
        COALESCE(
            (
                SELECT rp.payload_json
                FROM raw_products rp
                WHERE rp.run_id = {offer_alias}.run_id
                  AND (
                        ({offer_alias}.source_product_id IS NOT NULL AND rp.source_product_id = {offer_alias}.source_product_id)
                     OR ({offer_alias}.source_product_id IS NULL AND rp.source_name = {offer_alias}.display_name)
                  )
                ORDER BY rp.raw_id DESC
                LIMIT 1
            ),
            (
                SELECT rp.payload_json
                FROM shared_catalog_city_runs scr
                JOIN raw_products rp
                  ON rp.run_id = scr.seed_run_id
                WHERE scr.run_id = {offer_alias}.run_id
                  AND (
                        ({offer_alias}.source_product_id IS NOT NULL AND rp.source_product_id = {offer_alias}.source_product_id)
                     OR ({offer_alias}.source_product_id IS NULL AND rp.source_name = {offer_alias}.display_name)
                  )
                ORDER BY rp.raw_id DESC
                LIMIT 1
            )
        )
    """


def _extract_source_url(payload_json: Optional[str], fallback_url: Optional[str]) -> Optional[str]:
    if payload_json:
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            payload = None
        candidate = _scan_payload_for_source_url(payload)
        if candidate:
            return urljoin(fallback_url or "", candidate)
    return fallback_url


def _scan_payload_for_source_url(value: Any, key_hint: Optional[str] = None) -> Optional[str]:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).lower().replace("_", "")
            if any(token in normalized_key for token in ("image", "img", "resim", "thumb", "spotresim", "banner")):
                continue
            if normalized_key in SOURCE_URL_KEYS:
                found = _scan_payload_for_source_url(nested_value, key_hint=normalized_key)
                if found:
                    return found
            found = _scan_payload_for_source_url(nested_value, key_hint=normalized_key)
            if found:
                return found
        return None
    if isinstance(value, list):
        for item in value:
            found = _scan_payload_for_source_url(item, key_hint=key_hint)
            if found:
                return found
        return None
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        lowered = candidate.lower()
        if lowered.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")):
            return None
        looks_like_product_page = any(token in lowered for token in ("/product", "/urun", "/p-", "permalink", "detail"))
        if lowered.startswith(("http://", "https://")) and (key_hint in SOURCE_URL_KEYS or looks_like_product_page):
            return candidate
        if key_hint in SOURCE_URL_KEYS and (candidate.startswith("/") or ".html" in lowered or "/product" in lowered or "/urun" in lowered):
            return candidate
    return None


def _normalize_stock(availability: Optional[str]) -> bool:
    if availability is None:
        return True
    return str(availability).strip().lower() not in {"out_of_stock", "stokta yok", "false", "0"}


def _unit_price(active_price: float, size_value: Optional[float], size_unit: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    if active_price is None or not size_value or not size_unit:
        return None, None
    unit = str(size_unit).strip().lower()
    try:
        value = float(size_value)
    except (TypeError, ValueError):
        return None, None
    if value <= 0:
        return None, None

    if unit in {"g", "gr", "gram"}:
        return round(active_price / (value / 1000.0), 2), "kg"
    if unit in {"kg"}:
        return round(active_price / value, 2), "kg"
    if unit in {"ml"}:
        return round(active_price / (value / 1000.0), 2), "l"
    if unit in {"cl"}:
        return round(active_price / (value / 100.0), 2), "l"
    if unit in {"lt", "l", "litre", "liter"}:
        return round(active_price / value, 2), "l"
    if unit in {"adet", "ad", "pcs", "piece"}:
        return round(active_price / value, 2), "adet"
    return None, None


def _source_confidence(row: Dict[str, Any], requested_barcode: str, source_url: Optional[str]) -> float:
    direct_barcode = normalize_barcode(row.get("source_barcode"))
    primary_barcode = normalize_barcode(row.get("primary_barcode"))
    confidence = 0.75
    if direct_barcode == requested_barcode:
        confidence = 0.99
    elif primary_barcode == requested_barcode or row.get("canonical_id"):
        confidence = 0.93
    if source_url == row.get("entrypoint_url"):
        confidence = max(0.65, confidence - 0.08)
    return round(confidence, 2)


def _price_source_type(row: Dict[str, Any]) -> str:
    coverage_scope = (row.get("coverage_scope") or "").strip().lower()
    pricing_scope = (row.get("pricing_scope") or "").strip().lower()

    if coverage_scope in NATIONAL_COVERAGE_SCOPES:
        if pricing_scope in {"channel_and_warehouse", "channel_and_address"}:
            return "national_reference_price"
        return "national_reference_price"
    return "local_market_price"


def _contract_offer_payload(row: Dict[str, Any], requested_barcode: str) -> Dict[str, Any]:
    active_price = _active_price_value(row.get("listed_price"), row.get("promo_price"))
    source_url = _extract_source_url(row.get("payload_json"), row.get("entrypoint_url"))
    unit_price, unit_price_unit = (
        _unit_price(active_price, row.get("size_value"), row.get("size_unit"))
        if active_price is not None
        else (None, None)
    )
    return {
        "market_key": row["market_key"],
        "market_name": row["market_name"],
        "market_type": row["market_type"],
        "coverage_scope": row.get("coverage_scope"),
        "pricing_scope": row.get("pricing_scope"),
        "price_source_type": _price_source_type(row),
        "price": active_price,
        "currency": "TRY",
        "unit_price": unit_price,
        "unit_price_unit": unit_price_unit,
        "in_stock": _normalize_stock(row.get("availability")),
        "image_url": row.get("image_url"),
        "captured_at": row.get("observed_at"),
        "source_url": source_url,
        "source_confidence": _source_confidence(row, requested_barcode, source_url),
    }


def _summarize_offer_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "lowest_price": None,
            "highest_price": None,
            "median_price": None,
            "availability_ratio": 0.0,
            "last_seen_at": None,
            "markets_seen_count": 0,
        }
    prices = [
        _active_price_value(row.get("listed_price"), row.get("promo_price"))
        for row in rows
        if _active_price_value(row.get("listed_price"), row.get("promo_price")) is not None
    ]
    last_seen_at = max(row.get("observed_at") or "" for row in rows) or None
    available_count = sum(1 for row in rows if _normalize_stock(row.get("availability")))
    return {
        "lowest_price": round(min(prices), 2) if prices else None,
        "highest_price": round(max(prices), 2) if prices else None,
        "median_price": round(float(median(prices)), 2) if prices else None,
        "availability_ratio": round(available_count / len(rows), 4),
        "last_seen_at": last_seen_at,
        "markets_seen_count": len({row["market_key"] for row in rows}),
    }


def _price_change(connection: sqlite3.Connection, barcode: str, city_plate_code: Optional[int], days: int) -> Optional[float]:
    since = (datetime.utcnow() - timedelta(days=days)).replace(microsecond=0).isoformat() + "Z"
    params: List[Any] = [barcode, barcode, barcode, since]
    city_filter = ""
    if city_plate_code is not None:
        city_filter = " AND offers.city_plate_code = ?"
        params.append(city_plate_code)
    cursor = connection.execute(
        f"""
        WITH barcode_targets AS (
            SELECT canonical_id FROM canonical_product_barcodes WHERE barcode = ?
            UNION
            SELECT canonical_id FROM canonical_products WHERE primary_barcode = ?
        )
        SELECT
            COALESCE(offers.promo_price, offers.listed_price) AS active_price,
            offers.observed_at
        FROM effective_offers offers
        WHERE (offers.source_barcode = ? OR offers.canonical_id IN (SELECT canonical_id FROM barcode_targets))
          AND offers.observed_at >= ?
          {city_filter}
        ORDER BY offers.observed_at ASC
        """,
        params,
    )
    rows = _row_dicts(cursor)
    if len(rows) < 2:
        return None
    first = rows[0].get("active_price")
    last = rows[-1].get("active_price")
    if first is None or last is None:
        return None
    return round(float(last) - float(first), 2)


def _barcode_current_rows(
    connection: sqlite3.Connection,
    barcode: str,
    city_plate_code: Optional[int],
    include_out_of_stock: bool,
    limit: int,
) -> List[Dict[str, Any]]:
    where_clauses = [
        "(offers.source_barcode = ? OR offers.canonical_id IN (SELECT canonical_id FROM barcode_targets))",
    ]
    params: List[Any] = [barcode, barcode, barcode]
    if city_plate_code is not None:
        where_clauses.append("offers.city_plate_code = ?")
        params.append(city_plate_code)
    if not include_out_of_stock:
        where_clauses.append("COALESCE(offers.availability, 'in_stock') <> 'out_of_stock'")
    params.append(max(1, min(limit, 200)))
    cursor = connection.execute(
        f"""
        WITH barcode_targets AS (
            SELECT canonical_id FROM canonical_product_barcodes WHERE barcode = ?
            UNION
            SELECT canonical_id FROM canonical_products WHERE primary_barcode = ?
        )
        SELECT
            offers.market_key,
            offers.canonical_id,
            offers.source_product_id,
            offers.source_barcode,
            offers.display_name,
            offers.listed_price,
            offers.promo_price,
            offers.availability,
            offers.unit_label,
            offers.image_url,
            offers.observed_at,
            cities.plate_code AS city_code,
            cities.name AS city_name,
            cities.slug AS city_slug,
            sm.name AS market_name,
            sm.segment AS market_type,
            sm.coverage_scope,
            sm.pricing_scope,
            sm.entrypoint_url,
            cp.primary_barcode,
            cp.normalized_name,
            cp.brand,
            cp.category_l1,
            cp.size_value,
            cp.size_unit,
            {_canonical_offer_source_subquery("offers")} AS payload_json
        FROM current_offers offers
        JOIN cities ON cities.plate_code = offers.city_plate_code
        JOIN source_markets sm ON sm.market_key = offers.market_key
        LEFT JOIN canonical_products cp ON cp.canonical_id = offers.canonical_id
        WHERE {" AND ".join(where_clauses)}
        ORDER BY COALESCE(offers.promo_price, offers.listed_price) ASC, offers.observed_at DESC
        LIMIT ?
        """,
        params,
    )
    return _row_dicts(cursor)


def get_contract_product_offers(
    barcode: str,
    city_code: Optional[str] = None,
    district: Optional[str] = None,
    limit: int = 50,
    include_out_of_stock: bool = False,
) -> Dict[str, Any]:
    normalized_barcode = normalize_barcode(barcode)
    if normalized_barcode is None:
        raise ValueError("invalid_barcode")

    with connect() as connection:
        city = _resolve_city(connection, city_code)
        warnings: List[str] = []
        if district:
            warnings.append("district filter is not yet supported; city-level offers are returned")
        rows = _barcode_current_rows(
            connection=connection,
            barcode=normalized_barcode,
            city_plate_code=city["plate_code"] if city else None,
            include_out_of_stock=include_out_of_stock,
            limit=limit,
        )
        payload = {
            **_response_meta(connection, city_plate_code=city["plate_code"] if city else None, warnings=warnings),
            "barcode": normalized_barcode,
            "city": {"code": city["code"], "name": city["name"]} if city else None,
            "offers": [_contract_offer_payload(row, normalized_barcode) for row in rows],
            "analytics": {
                **_summarize_offer_rows(rows),
                "price_change_7d": _price_change(connection, normalized_barcode, city["plate_code"] if city else None, 7),
                "price_change_30d": _price_change(connection, normalized_barcode, city["plate_code"] if city else None, 30),
            },
        }
    return payload


def get_contract_price_history(
    barcode: str,
    city_code: Optional[str] = None,
    market_name: Optional[str] = None,
    days: int = 30,
) -> Dict[str, Any]:
    normalized_barcode = normalize_barcode(barcode)
    if normalized_barcode is None:
        raise ValueError("invalid_barcode")
    if days not in {7, 30, 90}:
        raise ValueError("invalid_days")

    cutoff = (datetime.utcnow() - timedelta(days=days)).replace(microsecond=0).isoformat() + "Z"
    with connect() as connection:
        city = _resolve_city(connection, city_code)
        where_clauses = [
            "(offers.source_barcode = ? OR offers.canonical_id IN (SELECT canonical_id FROM barcode_targets))",
            "offers.observed_at >= ?",
        ]
        params: List[Any] = [normalized_barcode, normalized_barcode, normalized_barcode, cutoff]
        if city is not None:
            where_clauses.append("offers.city_plate_code = ?")
            params.append(city["plate_code"])
        if market_name:
            where_clauses.append("LOWER(sm.name) = LOWER(?)")
            params.append(market_name)
        cursor = connection.execute(
            f"""
            WITH barcode_targets AS (
                SELECT canonical_id FROM canonical_product_barcodes WHERE barcode = ?
                UNION
                SELECT canonical_id FROM canonical_products WHERE primary_barcode = ?
            )
            SELECT
                sm.name AS market_name,
                offers.observed_at,
                COALESCE(offers.promo_price, offers.listed_price) AS active_price,
                offers.availability
            FROM effective_offers offers
            JOIN source_markets sm ON sm.market_key = offers.market_key
            WHERE {" AND ".join(where_clauses)}
            ORDER BY offers.observed_at ASC
            """,
            params,
        )
        rows = _row_dicts(cursor)
        return {
            **_response_meta(connection, city_plate_code=city["plate_code"] if city else None),
            "barcode": normalized_barcode,
            "market_name": market_name,
            "days": days,
            "history": [
                {
                    "market_name": row["market_name"],
                    "captured_at": row["observed_at"],
                    "price": row["active_price"],
                    "currency": "TRY",
                    "in_stock": _normalize_stock(row.get("availability")),
                }
                for row in rows
            ],
        }


def get_contract_pricing_alternatives(
    city_code: str,
    barcode: str,
    candidate_barcodes: List[str],
) -> Dict[str, Any]:
    normalized_barcode = normalize_barcode(barcode)
    if normalized_barcode is None:
        raise ValueError("invalid_barcode")
    normalized_candidates = []
    for candidate in candidate_barcodes:
        normalized_candidate = normalize_barcode(candidate)
        if normalized_candidate:
            normalized_candidates.append(normalized_candidate)

    with connect() as connection:
        city = _resolve_city(connection, city_code)
        if city is None:
            raise ValueError("invalid_city_code")

        def _barcode_summary(target_barcode: str) -> Dict[str, Any]:
            rows = _barcode_current_rows(
                connection=connection,
                barcode=target_barcode,
                city_plate_code=city["plate_code"],
                include_out_of_stock=True,
                limit=100,
            )
            return {
                "barcode": target_barcode,
                **_summarize_offer_rows(rows),
                "offers": [_contract_offer_payload(row, target_barcode) for row in rows[:20]],
                "price_change_7d": _price_change(connection, target_barcode, city["plate_code"], 7),
                "price_change_30d": _price_change(connection, target_barcode, city["plate_code"], 30),
            }

        return {
            **_response_meta(connection, city_plate_code=city["plate_code"]),
            "city": {"code": city["code"], "name": city["name"]},
            "barcode": normalized_barcode,
            "target": _barcode_summary(normalized_barcode),
            "alternatives": [_barcode_summary(candidate) for candidate in normalized_candidates],
        }


def search_contract_products(
    q: str,
    city_code: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    search_text = (q or "").strip()
    if not search_text:
        raise ValueError("q is required")

    with connect() as connection:
        city = _resolve_city(connection, city_code)
        where_clauses = [
            "(LOWER(offers.display_name) LIKE ? OR LOWER(COALESCE(cp.normalized_name, offers.display_name)) LIKE ?)"
        ]
        params: List[Any] = [f"%{search_text.lower()}%", f"%{search_text.lower()}%"]
        if city is not None:
            where_clauses.append("offers.city_plate_code = ?")
            params.append(city["plate_code"])
        if category:
            where_clauses.append("LOWER(COALESCE(cp.category_l1, '')) = ?")
            params.append(category.lower())
        if brand:
            where_clauses.append("LOWER(COALESCE(cp.brand, '')) = ?")
            params.append(brand.lower())
        params.append(max(1, min(limit, 100)))

        cursor = connection.execute(
            f"""
            SELECT
                offers.market_key,
                offers.canonical_id,
                offers.source_product_id,
                offers.source_barcode,
                offers.display_name,
                offers.listed_price,
                offers.promo_price,
                offers.availability,
                offers.unit_label,
                offers.image_url,
                offers.observed_at,
                sm.name AS market_name,
                sm.segment AS market_type,
                sm.coverage_scope,
                sm.pricing_scope,
                sm.entrypoint_url,
                cp.primary_barcode,
                cp.normalized_name,
                cp.brand,
                cp.category_l1,
                cp.size_value,
                cp.size_unit,
                {_canonical_offer_source_subquery("offers")} AS payload_json
            FROM current_offers offers
            JOIN source_markets sm ON sm.market_key = offers.market_key
            LEFT JOIN canonical_products cp ON cp.canonical_id = offers.canonical_id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY COALESCE(offers.promo_price, offers.listed_price) ASC, offers.observed_at DESC
            LIMIT ?
            """,
            params,
        )
        rows = _row_dicts(cursor)

        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            group_key = row.get("canonical_id") or row.get("source_barcode") or row["display_name"].lower()
            entry = grouped.setdefault(
                group_key,
                {
                    "barcode": row.get("primary_barcode") or row.get("source_barcode"),
                    "normalized_product_name": row.get("normalized_name") or row["display_name"],
                    "brand": row.get("brand"),
                    "normalized_category": row.get("category_l1"),
                    "pack_size": row.get("size_value"),
                    "pack_unit": row.get("size_unit"),
                    "image_url": row.get("image_url"),
                    "offers": [],
                },
            )
            barcode_for_offer = normalize_barcode(entry["barcode"]) or normalize_barcode(row.get("source_barcode")) or ""
            entry["offers"].append(_contract_offer_payload(row, barcode_for_offer))

        products: List[Dict[str, Any]] = []
        for entry in grouped.values():
            prices = [offer["price"] for offer in entry["offers"] if offer["price"] is not None]
            entry["lowest_price"] = round(min(prices), 2) if prices else None
            entry["highest_price"] = round(max(prices), 2) if prices else None
            entry["markets_seen_count"] = len({offer["market_name"] for offer in entry["offers"]})
            entry["offers"] = entry["offers"][:5]
            products.append(entry)

        products.sort(
            key=lambda item: (
                item["lowest_price"] is None,
                item["lowest_price"] if item["lowest_price"] is not None else 999999,
                -(item["markets_seen_count"] or 0),
                item["normalized_product_name"],
            )
        )

        return {
            **_response_meta(connection, city_plate_code=city["plate_code"] if city else None),
            "query": search_text,
            "city": {"code": city["code"], "name": city["name"]} if city else None,
            "products": products[: max(1, min(limit, 100))],
        }
