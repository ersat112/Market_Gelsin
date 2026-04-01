CREATE TABLE IF NOT EXISTS cities (
    plate_code INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS source_markets (
    market_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    segment TEXT NOT NULL,
    coverage_scope TEXT NOT NULL,
    pricing_scope TEXT NOT NULL,
    crawl_strategy TEXT NOT NULL,
    entrypoint_url TEXT NOT NULL,
    requires_address_seed INTEGER NOT NULL DEFAULT 0,
    refresh_hours INTEGER NOT NULL,
    official_notes TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS market_city_targets (
    target_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL,
    status TEXT NOT NULL,
    priority_score INTEGER NOT NULL,
    requires_address_seed INTEGER NOT NULL DEFAULT 0,
    probe_strategy TEXT NOT NULL,
    refresh_hours INTEGER NOT NULL,
    notes TEXT NOT NULL,
    UNIQUE(market_key, city_plate_code),
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key),
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code)
);

CREATE TABLE IF NOT EXISTS city_collection_program (
    city_plate_code INTEGER PRIMARY KEY,
    municipality_tier TEXT NOT NULL,
    local_launch_wave TEXT NOT NULL,
    coverage_goal TEXT NOT NULL,
    full_refresh_hours INTEGER NOT NULL,
    hot_refresh_hours INTEGER NOT NULL,
    history_mode TEXT NOT NULL,
    notes TEXT NOT NULL,
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code)
);

CREATE TABLE IF NOT EXISTS market_refresh_policy (
    market_key TEXT PRIMARY KEY,
    program_scope TEXT NOT NULL,
    launch_wave TEXT NOT NULL,
    full_refresh_hours INTEGER NOT NULL,
    hot_refresh_hours INTEGER NOT NULL,
    hot_refresh_enabled INTEGER NOT NULL DEFAULT 1,
    image_capture_policy TEXT NOT NULL,
    history_mode TEXT NOT NULL,
    notes TEXT NOT NULL,
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    address_fingerprint TEXT,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    stored_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    source_revision TEXT,
    notes TEXT,
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key),
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code)
);

CREATE TABLE IF NOT EXISTS raw_products (
    raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    source_product_id TEXT,
    source_barcode TEXT,
    source_category TEXT,
    source_name TEXT NOT NULL,
    source_brand TEXT,
    source_size TEXT,
    listed_price REAL NOT NULL,
    promo_price REAL,
    currency TEXT NOT NULL DEFAULT 'TRY',
    stock_status TEXT,
    image_url TEXT,
    payload_json TEXT,
    scraped_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id)
);

CREATE TABLE IF NOT EXISTS canonical_products (
    canonical_id TEXT PRIMARY KEY,
    primary_barcode TEXT,
    normalized_name TEXT NOT NULL,
    brand TEXT,
    size_value REAL,
    size_unit TEXT,
    category_l1 TEXT,
    category_l2 TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_product_barcodes (
    barcode TEXT PRIMARY KEY,
    canonical_id TEXT NOT NULL,
    barcode_type TEXT NOT NULL DEFAULT 'gtin',
    confidence_score REAL NOT NULL DEFAULT 1.0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY (canonical_id) REFERENCES canonical_products(canonical_id)
);

CREATE TABLE IF NOT EXISTS offers (
    offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_id TEXT,
    market_key TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL,
    source_product_id TEXT,
    source_barcode TEXT,
    display_name TEXT NOT NULL,
    listed_price REAL NOT NULL,
    promo_price REAL,
    availability TEXT,
    unit_label TEXT,
    image_url TEXT,
    observed_at TEXT NOT NULL,
    run_id INTEGER NOT NULL,
    FOREIGN KEY (canonical_id) REFERENCES canonical_products(canonical_id),
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key),
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code),
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id)
);

CREATE TABLE IF NOT EXISTS shared_catalog_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT NOT NULL,
    seed_run_id INTEGER NOT NULL UNIQUE,
    seed_city_plate_code INTEGER NOT NULL,
    observed_at TEXT NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key),
    FOREIGN KEY (seed_run_id) REFERENCES scrape_runs(run_id),
    FOREIGN KEY (seed_city_plate_code) REFERENCES cities(plate_code)
);

CREATE TABLE IF NOT EXISTS shared_catalog_snapshot_items (
    snapshot_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    canonical_id TEXT,
    source_product_id TEXT,
    source_barcode TEXT,
    display_name TEXT NOT NULL,
    listed_price REAL NOT NULL,
    promo_price REAL,
    availability TEXT,
    unit_label TEXT,
    image_url TEXT,
    observed_at TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES shared_catalog_snapshots(snapshot_id),
    FOREIGN KEY (canonical_id) REFERENCES canonical_products(canonical_id)
);

CREATE TABLE IF NOT EXISTS shared_catalog_city_runs (
    run_id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL,
    market_key TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL,
    seed_run_id INTEGER NOT NULL,
    cloned_at TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id),
    FOREIGN KEY (snapshot_id) REFERENCES shared_catalog_snapshots(snapshot_id),
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key),
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code),
    FOREIGN KEY (seed_run_id) REFERENCES scrape_runs(run_id),
    UNIQUE(snapshot_id, city_plate_code)
);

CREATE VIEW IF NOT EXISTS current_offers AS
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
FROM offers
INNER JOIN latest_successful_runs
    ON latest_successful_runs.run_id = offers.run_id;

CREATE INDEX IF NOT EXISTS idx_raw_products_source_barcode
ON raw_products(source_barcode);

CREATE INDEX IF NOT EXISTS idx_raw_products_run_product
ON raw_products(run_id, source_product_id);

CREATE INDEX IF NOT EXISTS idx_raw_products_run_name
ON raw_products(run_id, source_name);

CREATE INDEX IF NOT EXISTS idx_canonical_products_primary_barcode
ON canonical_products(primary_barcode);

CREATE INDEX IF NOT EXISTS idx_canonical_product_barcodes_canonical
ON canonical_product_barcodes(canonical_id);

CREATE INDEX IF NOT EXISTS idx_offers_source_barcode
ON offers(source_barcode);

CREATE INDEX IF NOT EXISTS idx_offers_canonical_id
ON offers(canonical_id);

CREATE INDEX IF NOT EXISTS idx_offers_city_barcode
ON offers(city_plate_code, source_barcode);

CREATE INDEX IF NOT EXISTS idx_offers_city_canonical
ON offers(city_plate_code, canonical_id);

CREATE INDEX IF NOT EXISTS idx_offers_observed_at
ON offers(observed_at);

CREATE INDEX IF NOT EXISTS idx_offers_run_market_city
ON offers(run_id, market_key, city_plate_code);

CREATE INDEX IF NOT EXISTS idx_shared_catalog_snapshots_market_seed
ON shared_catalog_snapshots(market_key, seed_run_id);

CREATE INDEX IF NOT EXISTS idx_shared_catalog_snapshot_items_snapshot
ON shared_catalog_snapshot_items(snapshot_id);

CREATE INDEX IF NOT EXISTS idx_shared_catalog_snapshot_items_barcode
ON shared_catalog_snapshot_items(source_barcode);

CREATE INDEX IF NOT EXISTS idx_shared_catalog_city_runs_market_city
ON shared_catalog_city_runs(market_key, city_plate_code, run_id);

CREATE INDEX IF NOT EXISTS idx_scrape_runs_status_market_city_run
ON scrape_runs(status, market_key, city_plate_code, run_id);

CREATE TABLE IF NOT EXISTS city_local_discovery_tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_plate_code INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL,
    priority_score INTEGER NOT NULL,
    notes TEXT NOT NULL,
    last_reviewed_at TEXT,
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code)
);

CREATE TABLE IF NOT EXISTS city_local_discovery_queries (
    query_id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_plate_code INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    query_kind TEXT NOT NULL,
    priority_score INTEGER NOT NULL,
    UNIQUE (city_plate_code, query_text),
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code)
);

CREATE TABLE IF NOT EXISTS city_local_coverage_status (
    city_plate_code INTEGER PRIMARY KEY,
    coverage_status TEXT NOT NULL,
    verified_market_count INTEGER NOT NULL,
    notes TEXT NOT NULL,
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code)
);

CREATE TABLE IF NOT EXISTS city_controlled_flow_plan (
    city_plate_code INTEGER PRIMARY KEY,
    rollout_stage TEXT NOT NULL,
    collection_mode TEXT NOT NULL,
    primary_market_key TEXT,
    fallback_market_key TEXT,
    verified_market_count INTEGER NOT NULL,
    live_market_count INTEGER NOT NULL,
    next_step TEXT NOT NULL,
    notes TEXT NOT NULL,
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code),
    FOREIGN KEY (primary_market_key) REFERENCES source_markets(market_key),
    FOREIGN KEY (fallback_market_key) REFERENCES source_markets(market_key)
);

CREATE TABLE IF NOT EXISTS market_adapter_readiness (
    market_key TEXT PRIMARY KEY,
    adapter_status TEXT NOT NULL,
    adapter_family TEXT NOT NULL,
    complexity_level TEXT NOT NULL,
    city_target_count INTEGER NOT NULL,
    priority_score INTEGER NOT NULL,
    notes TEXT NOT NULL,
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key)
);

CREATE TABLE IF NOT EXISTS adapter_onboarding_backlog (
    backlog_id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT NOT NULL UNIQUE,
    adapter_family TEXT NOT NULL,
    city_target_count INTEGER NOT NULL,
    complexity_level TEXT NOT NULL,
    recommended_next_step TEXT NOT NULL,
    priority_score INTEGER NOT NULL,
    notes TEXT NOT NULL,
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key)
);

CREATE TABLE IF NOT EXISTS barcode_scan_signals (
    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL DEFAULT 0,
    signal_date TEXT NOT NULL,
    scan_count INTEGER NOT NULL,
    source_app TEXT NOT NULL DEFAULT 'barkod_analiz',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (barcode, city_plate_code, signal_date, source_app)
);

CREATE TABLE IF NOT EXISTS barcode_scan_events (
    event_id TEXT PRIMARY KEY,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL DEFAULT 0,
    signal_date TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    scan_count INTEGER NOT NULL DEFAULT 1,
    source_app TEXT NOT NULL DEFAULT 'barkod_analiz',
    device_id TEXT,
    session_id TEXT,
    user_id TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hot_product_refresh_candidates (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL,
    market_key TEXT NOT NULL,
    scan_count INTEGER NOT NULL,
    matched_offer_count INTEGER NOT NULL DEFAULT 0,
    execution_mode TEXT NOT NULL,
    refresh_interval_hours INTEGER NOT NULL,
    refresh_due_at TEXT NOT NULL,
    last_signal_at TEXT NOT NULL,
    priority_score INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (barcode, city_plate_code, market_key),
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key)
);

CREATE TABLE IF NOT EXISTS local_market_candidates (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_plate_code INTEGER NOT NULL,
    market_name TEXT NOT NULL,
    market_slug TEXT NOT NULL UNIQUE,
    market_scope TEXT NOT NULL,
    entrypoint_url TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    source_type TEXT NOT NULL,
    notes TEXT NOT NULL,
    FOREIGN KEY (city_plate_code) REFERENCES cities(plate_code)
);

CREATE TABLE IF NOT EXISTS market_storefront_probes (
    market_key TEXT PRIMARY KEY,
    probe_scope TEXT NOT NULL,
    storefront_family TEXT NOT NULL,
    product_flow_status TEXT NOT NULL,
    recommended_adapter_family TEXT NOT NULL,
    homepage_url TEXT NOT NULL,
    final_url TEXT,
    http_status INTEGER,
    sample_url TEXT,
    sample_product_count INTEGER NOT NULL DEFAULT 0,
    signals_json TEXT NOT NULL,
    notes TEXT NOT NULL,
    last_probed_at TEXT NOT NULL,
    FOREIGN KEY (market_key) REFERENCES source_markets(market_key)
);

CREATE INDEX IF NOT EXISTS idx_city_collection_program_wave
ON city_collection_program(local_launch_wave);

CREATE INDEX IF NOT EXISTS idx_market_refresh_policy_scope
ON market_refresh_policy(program_scope, launch_wave);

CREATE INDEX IF NOT EXISTS idx_barcode_scan_signals_barcode_city_date
ON barcode_scan_signals(barcode, city_plate_code, signal_date);

CREATE INDEX IF NOT EXISTS idx_barcode_scan_events_barcode_city_date
ON barcode_scan_events(barcode, city_plate_code, signal_date);

CREATE INDEX IF NOT EXISTS idx_hot_refresh_candidates_status_due
ON hot_product_refresh_candidates(status, refresh_due_at, priority_score);
