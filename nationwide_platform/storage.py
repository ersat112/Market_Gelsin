import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, List, Union

from .adapter_backlog import build_adapter_backlog, build_adapter_readiness
from .cities import CITIES
from .collection_program import build_city_collection_programs, build_market_refresh_policies
from .city_rollout import build_city_controlled_flow_plans
from .local_discovery import (
    VERIFIED_LOCAL_MARKET_CANDIDATES,
    build_city_coverage_statuses,
    build_city_discovery_queries,
    build_city_discovery_tasks,
    city_plate_for_slug,
)
from .market_registry import MARKET_SOURCES
from .planner import CrawlTarget

if TYPE_CHECKING:
    from .storefront_probe import MarketStorefrontProbe


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schema.sql"
DEFAULT_DB_PATH = ROOT.parent / "turkiye_market_platform.db"


def connect(db_path: Union[str, Path] = DEFAULT_DB_PATH, timeout: float = 30.0) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path), timeout=timeout)
    connection.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA temp_store = MEMORY")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    connection.executescript(schema_sql)
    _ensure_column(connection, "raw_products", "source_barcode", "TEXT")
    _ensure_column(connection, "canonical_products", "primary_barcode", "TEXT")
    _ensure_column(connection, "offers", "source_barcode", "TEXT")
    _ensure_column(connection, "offers", "image_url", "TEXT")
    _refresh_current_offers_view(connection)
    _ensure_index(connection, "idx_raw_products_source_barcode", "raw_products(source_barcode)")
    _ensure_index(connection, "idx_raw_products_run_product", "raw_products(run_id, source_product_id)")
    _ensure_index(connection, "idx_raw_products_run_name", "raw_products(run_id, source_name)")
    _ensure_index(connection, "idx_canonical_products_primary_barcode", "canonical_products(primary_barcode)")
    _ensure_index(connection, "idx_canonical_product_barcodes_canonical", "canonical_product_barcodes(canonical_id)")
    _ensure_index(connection, "idx_offers_source_barcode", "offers(source_barcode)")
    _ensure_index(connection, "idx_offers_canonical_id", "offers(canonical_id)")
    _ensure_index(connection, "idx_offers_city_barcode", "offers(city_plate_code, source_barcode)")
    _ensure_index(connection, "idx_offers_city_canonical", "offers(city_plate_code, canonical_id)")
    _ensure_index(connection, "idx_offers_observed_at", "offers(observed_at)")
    _ensure_index(connection, "idx_offers_run_market_city", "offers(run_id, market_key, city_plate_code)")
    _ensure_index(connection, "idx_scrape_runs_status_market_city_run", "scrape_runs(status, market_key, city_plate_code, run_id)")
    _ensure_index(connection, "idx_shared_catalog_snapshots_market_seed", "shared_catalog_snapshots(market_key, seed_run_id)")
    _ensure_index(connection, "idx_shared_catalog_snapshot_items_snapshot", "shared_catalog_snapshot_items(snapshot_id)")
    _ensure_index(connection, "idx_shared_catalog_snapshot_items_barcode", "shared_catalog_snapshot_items(source_barcode)")
    _ensure_index(connection, "idx_shared_catalog_city_runs_market_city", "shared_catalog_city_runs(market_key, city_plate_code, run_id)")
    connection.commit()


def _ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in existing_columns:
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def _ensure_index(connection: sqlite3.Connection, index_name: str, target_sql: str) -> None:
    connection.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {target_sql}")


def _refresh_current_offers_view(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP VIEW IF EXISTS effective_offers;
        DROP VIEW IF EXISTS current_offers;
        CREATE VIEW effective_offers AS
        SELECT
            offers.offer_id,
            offers.canonical_id,
            offers.market_key,
            offers.city_plate_code,
            offers.source_product_id,
            offers.source_barcode,
            offers.display_name,
            offers.listed_price,
            offers.promo_price,
            offers.availability,
            offers.unit_label,
            COALESCE(
                offers.image_url,
                (
                    SELECT rp.image_url
                    FROM raw_products rp
                    WHERE rp.run_id = offers.run_id
                      AND (
                            (offers.source_product_id IS NOT NULL AND rp.source_product_id = offers.source_product_id)
                         OR (offers.source_product_id IS NULL AND rp.source_name = offers.display_name)
                      )
                    ORDER BY rp.raw_id DESC
                    LIMIT 1
                )
            ) AS image_url,
            offers.observed_at,
            offers.run_id
        FROM offers
        UNION ALL
        SELECT
            NULL AS offer_id,
            items.canonical_id,
            city_runs.market_key,
            city_runs.city_plate_code,
            items.source_product_id,
            items.source_barcode,
            items.display_name,
            items.listed_price,
            items.promo_price,
            items.availability,
            items.unit_label,
            items.image_url,
            items.observed_at,
            city_runs.run_id
        FROM shared_catalog_city_runs city_runs
        JOIN shared_catalog_snapshot_items items
            ON items.snapshot_id = city_runs.snapshot_id;
        CREATE VIEW current_offers AS
        WITH latest_successful_runs AS (
            SELECT
                market_key,
                city_plate_code,
                MAX(run_id) AS run_id
            FROM scrape_runs
            WHERE status IN ('completed', 'completed_with_errors')
            GROUP BY market_key, city_plate_code
        )
        SELECT
            offers.offer_id,
            offers.canonical_id,
            offers.market_key,
            offers.city_plate_code,
            offers.source_product_id,
            offers.source_barcode,
            offers.display_name,
            offers.listed_price,
            offers.promo_price,
            offers.availability,
            offers.unit_label,
            offers.image_url,
            offers.observed_at,
            offers.run_id
        FROM effective_offers offers
        INNER JOIN latest_successful_runs
            ON latest_successful_runs.run_id = offers.run_id;
        """
    )


def seed_cities(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO cities (plate_code, name, slug, region, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        [(city.plate_code, city.name, city.slug, city.region) for city in CITIES],
    )
    connection.commit()


def seed_markets(connection: sqlite3.Connection) -> None:
    current_market_keys = {market.key for market in MARKET_SOURCES}
    if current_market_keys:
        placeholders = ",".join("?" for _ in current_market_keys)
        connection.execute(
            f"DELETE FROM source_markets WHERE market_key NOT IN ({placeholders})",
            tuple(sorted(current_market_keys)),
        )
    connection.executemany(
        """
        INSERT OR REPLACE INTO source_markets (
            market_key,
            name,
            segment,
            coverage_scope,
            pricing_scope,
            crawl_strategy,
            entrypoint_url,
            requires_address_seed,
            refresh_hours,
            official_notes,
            is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        [
            (
                market.key,
                market.name,
                market.segment,
                market.coverage_scope,
                market.pricing_scope,
                market.crawl_strategy,
                market.entrypoint_url,
                int(market.requires_address_seed),
                market.refresh_hours,
                market.official_notes,
            )
            for market in MARKET_SOURCES
        ],
    )
    connection.commit()


def seed_targets(connection: sqlite3.Connection, targets: List[CrawlTarget]) -> None:
    connection.execute("DELETE FROM market_city_targets")
    connection.executemany(
        """
        INSERT OR REPLACE INTO market_city_targets (
            market_key,
            city_plate_code,
            status,
            priority_score,
            requires_address_seed,
            probe_strategy,
            refresh_hours,
            notes
        )
        VALUES (?, ?, 'planned', ?, ?, ?, ?, ?)
        """,
        [
            (
                target.market_key,
                target.city_plate_code,
                target.priority_score,
                int(target.requires_address_seed),
                target.probe_strategy,
                target.refresh_hours,
                target.notes,
            )
            for target in targets
        ],
    )
    connection.commit()


def seed_city_collection_program(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM city_collection_program")
    connection.executemany(
        """
        INSERT INTO city_collection_program (
            city_plate_code,
            municipality_tier,
            local_launch_wave,
            coverage_goal,
            full_refresh_hours,
            hot_refresh_hours,
            history_mode,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                program.city_plate_code,
                program.municipality_tier,
                program.local_launch_wave,
                program.coverage_goal,
                program.full_refresh_hours,
                program.hot_refresh_hours,
                program.history_mode,
                program.notes,
            )
            for program in build_city_collection_programs()
        ],
    )
    connection.commit()


def seed_market_refresh_policy(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM market_refresh_policy")
    connection.executemany(
        """
        INSERT INTO market_refresh_policy (
            market_key,
            program_scope,
            launch_wave,
            full_refresh_hours,
            hot_refresh_hours,
            hot_refresh_enabled,
            image_capture_policy,
            history_mode,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                policy.market_key,
                policy.program_scope,
                policy.launch_wave,
                policy.full_refresh_hours,
                policy.hot_refresh_hours,
                int(policy.hot_refresh_enabled),
                policy.image_capture_policy,
                policy.history_mode,
                policy.notes,
            )
            for policy in build_market_refresh_policies()
        ],
    )
    connection.commit()


def seed_city_discovery_tasks(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM city_local_discovery_tasks")
    connection.executemany(
        """
        INSERT INTO city_local_discovery_tasks (
            city_plate_code,
            status,
            priority_score,
            notes,
            last_reviewed_at
        )
        VALUES (?, ?, ?, ?, NULL)
        """,
        [
            (
                task.city_plate_code,
                task.status,
                task.priority_score,
                task.notes,
            )
            for task in build_city_discovery_tasks()
        ],
    )
    connection.commit()


def seed_city_discovery_queries(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM city_local_discovery_queries")
    connection.executemany(
        """
        INSERT INTO city_local_discovery_queries (
            city_plate_code,
            query_text,
            query_kind,
            priority_score
        )
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                query.city_plate_code,
                query.query_text,
                query.query_kind,
                query.priority_score,
            )
            for query in build_city_discovery_queries()
        ],
    )
    connection.commit()


def seed_city_coverage_status(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM city_local_coverage_status")
    connection.executemany(
        """
        INSERT INTO city_local_coverage_status (
            city_plate_code,
            coverage_status,
            verified_market_count,
            notes
        )
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                status.city_plate_code,
                status.coverage_status,
                status.verified_market_count,
                status.notes,
            )
            for status in build_city_coverage_statuses()
        ],
    )
    connection.commit()


def seed_city_controlled_flow_plan(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM city_controlled_flow_plan")
    connection.executemany(
        """
        INSERT INTO city_controlled_flow_plan (
            city_plate_code,
            rollout_stage,
            collection_mode,
            primary_market_key,
            fallback_market_key,
            verified_market_count,
            live_market_count,
            next_step,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                plan.city_plate_code,
                plan.rollout_stage,
                plan.collection_mode,
                plan.primary_market_key,
                plan.fallback_market_key,
                plan.verified_market_count,
                plan.live_market_count,
                plan.next_step,
                plan.notes,
            )
            for plan in build_city_controlled_flow_plans()
        ],
    )
    connection.commit()


def seed_market_adapter_readiness(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM market_adapter_readiness")
    connection.executemany(
        """
        INSERT INTO market_adapter_readiness (
            market_key,
            adapter_status,
            adapter_family,
            complexity_level,
            city_target_count,
            priority_score,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                readiness.market_key,
                readiness.adapter_status,
                readiness.adapter_family,
                readiness.complexity_level,
                readiness.city_target_count,
                readiness.priority_score,
                readiness.notes,
            )
            for readiness in build_adapter_readiness()
        ],
    )
    connection.commit()


def seed_adapter_onboarding_backlog(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM adapter_onboarding_backlog")
    connection.executemany(
        """
        INSERT INTO adapter_onboarding_backlog (
            market_key,
            adapter_family,
            city_target_count,
            complexity_level,
            recommended_next_step,
            priority_score,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.market_key,
                item.adapter_family,
                item.city_target_count,
                item.complexity_level,
                item.recommended_next_step,
                item.priority_score,
                item.notes,
            )
            for item in build_adapter_backlog()
        ],
    )
    connection.commit()


def seed_local_market_candidates(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM local_market_candidates")
    connection.executemany(
        """
        INSERT INTO local_market_candidates (
            city_plate_code,
            market_name,
            market_slug,
            market_scope,
            entrypoint_url,
            evidence_url,
            verification_status,
            source_type,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                city_plate_for_slug(candidate.city_slug),
                candidate.market_name,
                candidate.market_slug,
                candidate.market_scope,
                candidate.entrypoint_url,
                candidate.evidence_url,
                candidate.verification_status,
                candidate.source_type,
                candidate.notes,
            )
            for candidate in VERIFIED_LOCAL_MARKET_CANDIDATES
        ],
    )
    connection.commit()


def upsert_market_storefront_probes(
    connection: sqlite3.Connection,
    probes: List["MarketStorefrontProbe"],
) -> None:
    connection.execute("DELETE FROM market_storefront_probes")
    connection.executemany(
        """
        INSERT OR REPLACE INTO market_storefront_probes (
            market_key,
            probe_scope,
            storefront_family,
            product_flow_status,
            recommended_adapter_family,
            homepage_url,
            final_url,
            http_status,
            sample_url,
            sample_product_count,
            signals_json,
            notes,
            last_probed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                probe.market_key,
                probe.probe_scope,
                probe.storefront_family,
                probe.product_flow_status,
                probe.recommended_adapter_family,
                probe.homepage_url,
                probe.final_url,
                probe.http_status,
                probe.sample_url,
                probe.sample_product_count,
                probe.signals_json,
                probe.notes,
                probe.last_probed_at,
            )
            for probe in probes
        ],
    )
    connection.commit()
