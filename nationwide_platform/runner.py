import json
from datetime import datetime
from typing import Iterable, List, Optional

from .adapters import FetchContext, RawOffer, get_adapter
from .bootstrap import bootstrap_database
from .cities import CITY_BY_SLUG
from .normalization import extract_barcode_candidates, normalize_barcode, normalize_product_name
from .storage import connect


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _insert_scrape_run(connection, market_key: str, city_plate_code: int, notes: Optional[str] = None) -> int:
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO scrape_runs (
            market_key,
            city_plate_code,
            started_at,
            status,
            notes
        )
        VALUES (?, ?, ?, 'running', ?)
        """,
        (market_key, city_plate_code, _now(), notes),
    )
    connection.commit()
    return int(cursor.lastrowid)


def _finalize_scrape_run(connection, run_id: int, fetched_count: int, stored_count: int, error_count: int) -> None:
    _finalize_scrape_run_with_status(
        connection=connection,
        run_id=run_id,
        status="completed",
        fetched_count=fetched_count,
        stored_count=stored_count,
        error_count=error_count,
        notes=None,
    )


def _finalize_scrape_run_with_status(
    connection,
    run_id: int,
    status: str,
    fetched_count: int,
    stored_count: int,
    error_count: int,
    notes: Optional[str],
) -> None:
    connection.execute(
        """
        UPDATE scrape_runs
        SET finished_at = ?, status = ?, fetched_count = ?, stored_count = ?, error_count = ?, notes = COALESCE(?, notes)
        WHERE run_id = ?
        """,
        (_now(), status, fetched_count, stored_count, error_count, notes, run_id),
    )
    connection.commit()


BARCODE_KEYS = {
    "barcode",
    "barkod",
    "ean",
    "ean8",
    "ean13",
    "gtin",
    "gtin8",
    "gtin12",
    "gtin13",
    "gtin14",
    "upc",
    "upca",
    "upce",
    "productbarcode",
    "combinationbarcode",
}


def _extract_barcode_from_payload(payload_json: Optional[str]) -> Optional[str]:
    if not payload_json:
        return None
    try:
        payload = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        return None
    return _scan_payload_for_barcode(payload)


def _scan_payload_for_barcode(value, key_hint: Optional[str] = None) -> Optional[str]:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).lower().replace("_", "")
            if normalized_key in BARCODE_KEYS:
                barcode = normalize_barcode(str(nested_value))
                if barcode:
                    return barcode
            next_hint = normalized_key if normalized_key in BARCODE_KEYS else None
            barcode = _scan_payload_for_barcode(nested_value, key_hint=next_hint)
            if barcode:
                return barcode
        return None
    if isinstance(value, list):
        for item in value:
            barcode = _scan_payload_for_barcode(item, key_hint=key_hint)
            if barcode:
                return barcode
        return None
    if isinstance(value, str):
        if key_hint not in BARCODE_KEYS:
            return None
        matches = extract_barcode_candidates(value, strict=True)
        return matches[0] if matches else None
    return None


def _infer_offer_barcode(raw_offer: RawOffer) -> Optional[str]:
    direct_barcode = normalize_barcode(raw_offer.source_barcode)
    if direct_barcode:
        return direct_barcode

    payload_barcode = _extract_barcode_from_payload(raw_offer.payload_json)
    if payload_barcode:
        return payload_barcode

    # Merchant product ids are often numeric SKUs. Only trust source ids when they look
    # like longer GTIN families, not short 8-digit storefront ids.
    source_product_barcode = _coerce_product_id_barcode(raw_offer.source_product_id)
    if source_product_barcode:
        return source_product_barcode

    for candidate in _iter_barcode_text_candidates(raw_offer):
        barcode = normalize_barcode(candidate, strict=True)
        if barcode:
            return barcode
    return None


def _iter_barcode_text_candidates(raw_offer: RawOffer) -> Iterable[str]:
    if raw_offer.source_name:
        yield raw_offer.source_name
    if raw_offer.source_brand:
        yield raw_offer.source_brand
    if raw_offer.source_size:
        yield raw_offer.source_size


def _coerce_product_id_barcode(value: Optional[str]) -> Optional[str]:
    barcode = normalize_barcode(value, strict=True)
    if not barcode:
        return None
    if len(barcode) not in {12, 13, 14}:
        return None
    return barcode


def _canonical_id_for_offer(raw_offer: RawOffer, barcode: Optional[str]) -> str:
    if barcode:
        return f"bc:{barcode}"
    return normalize_product_name(raw_offer.source_name).fingerprint


def _upsert_canonical_product(connection, raw_offer: RawOffer) -> tuple[str, Optional[str]]:
    normalized = normalize_product_name(raw_offer.source_name)
    source_barcode = _infer_offer_barcode(raw_offer)
    canonical_id = _canonical_id_for_offer(raw_offer, source_barcode)
    connection.execute(
        """
        INSERT INTO canonical_products (
            canonical_id,
            primary_barcode,
            normalized_name,
            brand,
            size_value,
            size_unit,
            category_l1,
            category_l2,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_id) DO UPDATE SET
            primary_barcode = COALESCE(canonical_products.primary_barcode, excluded.primary_barcode),
            normalized_name = excluded.normalized_name,
            brand = excluded.brand,
            size_value = excluded.size_value,
            size_unit = excluded.size_unit,
            category_l1 = excluded.category_l1,
            category_l2 = excluded.category_l2,
            updated_at = excluded.updated_at
        """,
        (
            canonical_id,
            source_barcode,
            normalized.normalized_name,
            raw_offer.source_brand,
            normalized.size_value,
            normalized.size_unit,
            raw_offer.source_category,
            None,
            _now(),
            _now(),
        ),
    )
    if source_barcode:
        connection.execute(
            """
            INSERT INTO canonical_product_barcodes (
                barcode,
                canonical_id,
                barcode_type,
                confidence_score,
                first_seen_at,
                last_seen_at
            )
            VALUES (?, ?, 'gtin', 1.0, ?, ?)
            ON CONFLICT(barcode) DO UPDATE SET
                canonical_id = excluded.canonical_id,
                last_seen_at = excluded.last_seen_at
            """,
            (source_barcode, canonical_id, _now(), _now()),
        )
    return canonical_id, source_barcode


def _store_offer(connection, run_id: int, market_key: str, city_plate_code: int, raw_offer: RawOffer) -> None:
    scraped_at = _now()
    source_barcode = _infer_offer_barcode(raw_offer)
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO raw_products (
            run_id,
            source_product_id,
            source_barcode,
            source_category,
            source_name,
            source_brand,
            source_size,
            listed_price,
            promo_price,
            currency,
            stock_status,
            image_url,
            payload_json,
            scraped_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'TRY', ?, ?, ?, ?)
        """,
        (
            run_id,
            raw_offer.source_product_id,
            source_barcode,
            raw_offer.source_category,
            raw_offer.source_name,
            raw_offer.source_brand,
            raw_offer.source_size,
            raw_offer.listed_price,
            raw_offer.promo_price,
            raw_offer.stock_status,
            raw_offer.image_url,
            raw_offer.payload_json,
            scraped_at,
        ),
    )
    canonical_id, source_barcode = _upsert_canonical_product(connection, raw_offer)
    connection.execute(
        """
        INSERT INTO offers (
            canonical_id,
            market_key,
            city_plate_code,
            source_product_id,
            source_barcode,
            display_name,
            listed_price,
            promo_price,
            availability,
            unit_label,
            image_url,
            observed_at,
            run_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            canonical_id,
            market_key,
            city_plate_code,
            raw_offer.source_product_id,
            source_barcode,
            raw_offer.source_name,
            raw_offer.listed_price,
            raw_offer.promo_price,
            raw_offer.stock_status,
            raw_offer.source_size,
            raw_offer.image_url,
            scraped_at,
            run_id,
        ),
    )


def _ensure_shared_catalog_snapshot(
    connection,
    market_key: str,
    seed_run_id: int,
    seed_city_plate_code: int,
) -> tuple[int, int]:
    existing = connection.execute(
        """
        SELECT snapshot_id, item_count
        FROM shared_catalog_snapshots
        WHERE seed_run_id = ?
        """,
        (seed_run_id,),
    ).fetchone()
    if existing is not None:
        return int(existing[0]), int(existing[1] or 0)

    observed_at_row = connection.execute(
        """
        SELECT COALESCE(MAX(observed_at), ?)
        FROM offers
        WHERE run_id = ?
        """,
        (_now(), seed_run_id),
    ).fetchone()
    observed_at = str(observed_at_row[0] or _now())
    created_at = _now()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO shared_catalog_snapshots (
            market_key,
            seed_run_id,
            seed_city_plate_code,
            observed_at,
            item_count,
            created_at,
            updated_at,
            notes
        )
        VALUES (?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            market_key,
            seed_run_id,
            seed_city_plate_code,
            observed_at,
            created_at,
            created_at,
            f"seed_run:{seed_run_id}",
        ),
    )
    snapshot_id = int(cursor.lastrowid)
    connection.execute(
        """
        INSERT INTO shared_catalog_snapshot_items (
            snapshot_id,
            canonical_id,
            source_product_id,
            source_barcode,
            display_name,
            listed_price,
            promo_price,
            availability,
            unit_label,
            image_url,
            observed_at
        )
        SELECT
            ?,
            canonical_id,
            source_product_id,
            source_barcode,
            display_name,
            listed_price,
            promo_price,
            availability,
            unit_label,
            image_url,
            observed_at
        FROM offers
        WHERE run_id = ?
        """,
        (snapshot_id, seed_run_id),
    )
    item_count_row = connection.execute(
        "SELECT COUNT(*) FROM shared_catalog_snapshot_items WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    item_count = int(item_count_row[0] or 0)
    connection.execute(
        """
        UPDATE shared_catalog_snapshots
        SET item_count = ?, updated_at = ?
        WHERE snapshot_id = ?
        """,
        (item_count, _now(), snapshot_id),
    )
    return snapshot_id, item_count
def _persist_offers_for_run(
    connection,
    run_id: int,
    market_key: str,
    city_plate_code: int,
    offers: List[RawOffer],
) -> tuple[int, int, str]:
    stored_count = 0
    error_count = 0
    connection.execute("BEGIN")
    try:
        for offer in offers:
            try:
                _store_offer(connection, run_id, market_key, city_plate_code, offer)
                stored_count += 1
            except Exception:
                error_count += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    status = "completed_with_errors" if error_count else "completed"
    notes = f"{error_count} offer could not be stored." if error_count else None
    _finalize_scrape_run_with_status(
        connection=connection,
        run_id=run_id,
        status=status,
        fetched_count=len(offers),
        stored_count=stored_count,
        error_count=error_count,
        notes=notes,
    )
    return stored_count, error_count, status


def _build_fetch_context(
    market_key: str,
    city_slug: str,
    address_label: Optional[str] = None,
    district: Optional[str] = None,
    neighborhood: Optional[str] = None,
) -> tuple[object, FetchContext]:
    city = CITY_BY_SLUG[city_slug]
    context = FetchContext(
        market_key=market_key,
        city_name=city.name,
        city_plate_code=city.plate_code,
        address_label=address_label,
        district=district,
        neighborhood=neighborhood,
    )
    return city, context


def fetch_market_offers(
    market_key: str,
    city_slug: str,
    address_label: Optional[str] = None,
    district: Optional[str] = None,
    neighborhood: Optional[str] = None,
    bootstrap: bool = True,
) -> List[RawOffer]:
    if bootstrap:
        bootstrap_database()
    _, context = _build_fetch_context(
        market_key=market_key,
        city_slug=city_slug,
        address_label=address_label,
        district=district,
        neighborhood=neighborhood,
    )
    adapter = get_adapter(market_key)
    return adapter.fetch_offers(context)


def store_prefetched_market_collection(
    market_key: str,
    city_slug: str,
    offers: List[RawOffer],
    address_label: Optional[str] = None,
    bootstrap: bool = True,
) -> dict:
    if bootstrap:
        bootstrap_database()
    city, _ = _build_fetch_context(
        market_key=market_key,
        city_slug=city_slug,
        address_label=address_label,
    )

    with connect() as connection:
        run_id = _insert_scrape_run(connection, market_key, city.plate_code, notes=address_label)
        try:
            stored_count, error_count, status = _persist_offers_for_run(
                connection=connection,
                run_id=run_id,
                market_key=market_key,
                city_plate_code=city.plate_code,
                offers=offers,
            )
        except Exception as exc:
            _finalize_scrape_run_with_status(
                connection=connection,
                run_id=run_id,
                status="failed",
                fetched_count=len(offers),
                stored_count=0,
                error_count=1,
                notes=str(exc)[:500],
            )
            raise

    return {
        "run_id": run_id,
        "market_key": market_key,
        "city_slug": city_slug,
        "fetched_count": len(offers),
        "stored_count": stored_count,
        "error_count": error_count,
        "status": status,
    }


def clone_market_collection_from_seed(
    seed_run_id: int,
    market_key: str,
    city_slug: str,
    address_label: Optional[str] = None,
    bootstrap: bool = True,
) -> dict:
    if bootstrap:
        bootstrap_database()
    city, _ = _build_fetch_context(
        market_key=market_key,
        city_slug=city_slug,
        address_label=address_label,
    )

    with connect() as connection:
        seed_row = connection.execute(
            """
            SELECT fetched_count, stored_count, error_count, status, city_plate_code
            FROM scrape_runs
            WHERE run_id = ? AND market_key = ?
            """,
            (seed_run_id, market_key),
        ).fetchone()
        if seed_row is None:
            raise ValueError(f"Seed run not found for {market_key}: {seed_run_id}")

        fetched_count = int(seed_row[0] or 0)
        stored_count = int(seed_row[1] or 0)
        error_count = int(seed_row[2] or 0)
        seed_status = str(seed_row[3] or "completed")
        seed_city_plate_code = int(seed_row[4])
        if seed_status not in {"completed", "completed_with_errors"}:
            raise ValueError(f"Seed run is not in a cloneable status: {seed_status}")

        run_id = _insert_scrape_run(connection, market_key, city.plate_code, notes=address_label)
        try:
            snapshot_id, snapshot_item_count = _ensure_shared_catalog_snapshot(
                connection=connection,
                market_key=market_key,
                seed_run_id=seed_run_id,
                seed_city_plate_code=seed_city_plate_code,
            )
            connection.commit()
            connection.execute("BEGIN")
            connection.execute(
                """
                INSERT INTO shared_catalog_city_runs (
                    run_id,
                    snapshot_id,
                    market_key,
                    city_plate_code,
                    seed_run_id,
                    cloned_at,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    snapshot_id,
                    market_key,
                    city.plate_code,
                    seed_run_id,
                    _now(),
                    address_label or f"shared_snapshot:{snapshot_id}",
                ),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            _finalize_scrape_run_with_status(
                connection=connection,
                run_id=run_id,
                status="failed",
                fetched_count=fetched_count,
                stored_count=0,
                error_count=1,
                notes=str(exc)[:500],
            )
            raise

        status = "completed_with_errors" if error_count else "completed"
        notes = address_label or f"shared_snapshot:{snapshot_id}"
        if error_count:
            notes = f"{notes} | seed_error_count={error_count}"
        _finalize_scrape_run_with_status(
            connection=connection,
            run_id=run_id,
            status=status,
            fetched_count=fetched_count,
            stored_count=snapshot_item_count,
            error_count=error_count,
            notes=notes,
        )

    return {
        "run_id": run_id,
        "market_key": market_key,
        "city_slug": city_slug,
        "fetched_count": fetched_count,
        "stored_count": snapshot_item_count,
        "error_count": error_count,
        "status": status,
    }


def bulk_clone_market_collection_from_seed(
    seed_run_id: int,
    market_key: str,
    city_slugs: List[str],
    address_label: Optional[str] = None,
    bootstrap: bool = True,
) -> dict:
    if bootstrap:
        bootstrap_database()

    target_cities = []
    for city_slug in city_slugs:
        city, _ = _build_fetch_context(
            market_key=market_key,
            city_slug=city_slug,
            address_label=address_label,
        )
        target_cities.append(city)

    with connect() as connection:
        seed_row = connection.execute(
            """
            SELECT fetched_count, stored_count, error_count, status, city_plate_code
            FROM scrape_runs
            WHERE run_id = ? AND market_key = ?
            """,
            (seed_run_id, market_key),
        ).fetchone()
        if seed_row is None:
            raise ValueError(f"Seed run not found for {market_key}: {seed_run_id}")

        fetched_count = int(seed_row[0] or 0)
        stored_count = int(seed_row[1] or 0)
        error_count = int(seed_row[2] or 0)
        seed_status = str(seed_row[3] or "completed")
        seed_city_plate_code = int(seed_row[4])
        if seed_status not in {"completed", "completed_with_errors"}:
            raise ValueError(f"Seed run is not in a cloneable status: {seed_status}")

        started_at = _now()
        batch_note = f"{address_label or 'shared_catalog_seed'} | bulk_seed_run:{seed_run_id} | started_at:{started_at}"
        status = "completed_with_errors" if error_count else "completed"
        snapshot_id, snapshot_item_count = _ensure_shared_catalog_snapshot(
            connection=connection,
            market_key=market_key,
            seed_run_id=seed_run_id,
            seed_city_plate_code=seed_city_plate_code,
        )
        connection.commit()

        connection.execute("BEGIN")
        try:
            connection.executemany(
                """
                INSERT INTO scrape_runs (
                    market_key,
                    city_plate_code,
                    started_at,
                    status,
                    notes
                )
                VALUES (?, ?, ?, 'running', ?)
                """,
                [
                    (market_key, city.plate_code, started_at, batch_note)
                    for city in target_cities
                ],
            )
            run_rows = connection.execute(
                """
                SELECT run_id, city_plate_code
                FROM scrape_runs
                WHERE market_key = ?
                  AND started_at = ?
                  AND notes = ?
                  AND status = 'running'
                ORDER BY city_plate_code
                """,
                (market_key, started_at, batch_note),
            ).fetchall()

            connection.execute(
                """
                INSERT INTO shared_catalog_city_runs (
                    run_id,
                    snapshot_id,
                    market_key,
                    city_plate_code,
                    seed_run_id,
                    cloned_at,
                    notes
                )
                SELECT
                    clone_runs.run_id,
                    ?,
                    ?,
                    clone_runs.city_plate_code,
                    ?,
                    ?,
                    ?
                FROM (
                    SELECT run_id, city_plate_code
                    FROM scrape_runs
                    WHERE market_key = ?
                      AND started_at = ?
                      AND notes = ?
                      AND status = 'running'
                ) AS clone_runs
                """,
                (
                    snapshot_id,
                    market_key,
                    seed_run_id,
                    _now(),
                    batch_note,
                    market_key,
                    started_at,
                    batch_note,
                ),
            )

            finished_at = _now()
            connection.executemany(
                """
                UPDATE scrape_runs
                SET finished_at = ?, status = ?, fetched_count = ?, stored_count = ?, error_count = ?, notes = ?
                WHERE run_id = ?
                """,
                [
                    (finished_at, status, fetched_count, snapshot_item_count, error_count, batch_note, run_id)
                    for run_id, _ in run_rows
                ],
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return {
        "market_key": market_key,
        "seed_run_id": seed_run_id,
        "city_count": len(target_cities),
        "fetched_count": fetched_count,
        "stored_count_per_city": snapshot_item_count,
        "total_stored_count": snapshot_item_count * len(target_cities),
        "status": status,
    }


def run_market_collection(
    market_key: str,
    city_slug: str,
    address_label: Optional[str] = None,
    district: Optional[str] = None,
    neighborhood: Optional[str] = None,
    bootstrap: bool = True,
) -> dict:
    if bootstrap:
        bootstrap_database()
    city, context = _build_fetch_context(
        market_key=market_key,
        city_slug=city_slug,
        address_label=address_label,
        district=district,
        neighborhood=neighborhood,
    )
    adapter = get_adapter(market_key)

    with connect() as connection:
        run_id = _insert_scrape_run(connection, market_key, city.plate_code, notes=address_label)
        offers: List[RawOffer] = []
        stored_count = 0
        error_count = 0
        status = "failed"
        try:
            offers = adapter.fetch_offers(context)
            stored_count, error_count, status = _persist_offers_for_run(
                connection=connection,
                run_id=run_id,
                market_key=market_key,
                city_plate_code=city.plate_code,
                offers=offers,
            )
        except Exception as exc:
            _finalize_scrape_run_with_status(
                connection=connection,
                run_id=run_id,
                status="failed",
                fetched_count=len(offers),
                stored_count=stored_count,
                error_count=error_count + 1,
                notes=str(exc)[:500],
            )
            raise

    return {
        "run_id": run_id,
        "market_key": market_key,
        "city_slug": city_slug,
        "fetched_count": len(offers),
        "stored_count": stored_count,
        "error_count": error_count,
        "status": status,
    }
