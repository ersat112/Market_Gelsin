DROP MATERIALIZED VIEW IF EXISTS mg_product_price_trends CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mg_product_best_offers CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mg_product_city_summary CASCADE;
DROP VIEW IF EXISTS mg_price_history CASCADE;
DROP VIEW IF EXISTS mg_market_offers CASCADE;
DROP VIEW IF EXISTS mg_markets CASCADE;
DROP VIEW IF EXISTS mg_products CASCADE;

CREATE VIEW mg_products AS
WITH latest_images AS (
    SELECT DISTINCT ON (COALESCE(canonical_id, source_barcode, display_name))
        canonical_id,
        source_barcode,
        display_name,
        image_url,
        observed_at
    FROM current_offers
    WHERE image_url IS NOT NULL
      AND image_url <> ''
    ORDER BY COALESCE(canonical_id, source_barcode, display_name), observed_at DESC
)
SELECT
    cp.canonical_id AS id,
    COALESCE(cp.primary_barcode, fallback_barcode.barcode) AS barcode,
    cp.normalized_name AS normalized_product_name,
    cp.brand,
    cp.category_l1 AS normalized_category,
    cp.size_value AS pack_size,
    cp.size_unit AS pack_unit,
    latest_images.image_url,
    cp.created_at,
    cp.updated_at
FROM canonical_products cp
LEFT JOIN LATERAL (
    SELECT barcode
    FROM canonical_product_barcodes cb
    WHERE cb.canonical_id = cp.canonical_id
    ORDER BY cb.barcode
    LIMIT 1
) AS fallback_barcode ON TRUE
LEFT JOIN latest_images
    ON latest_images.canonical_id = cp.canonical_id;

CREATE VIEW mg_markets AS
SELECT
    sm.market_key || ':' || LPAD(c.plate_code::text, 2, '0') AS id,
    sm.market_key,
    sm.name AS market_name,
    sm.market_key AS market_slug,
    sm.segment AS market_type,
    CASE
        WHEN sm.segment = 'regional_chain' THEN TRUE
        WHEN sm.coverage_scope IN ('city_specific', 'district_cluster') THEN TRUE
        ELSE FALSE
    END AS is_local_market,
    LPAD(c.plate_code::text, 2, '0') AS city_code,
    c.name AS city_name,
    NULL::text AS district_name,
    sm.market_key AS source_name,
    (sm.is_active = 1) AS is_active,
    sm.coverage_scope,
    sm.pricing_scope,
    sm.entrypoint_url
FROM market_city_targets mt
JOIN source_markets sm
    ON sm.market_key = mt.market_key
JOIN cities c
    ON c.plate_code = mt.city_plate_code
WHERE sm.is_active = 1;

CREATE VIEW mg_market_offers AS
SELECT
    COALESCE(current_offers.offer_id::text, md5(
        current_offers.market_key || '|' ||
        LPAD(cities.plate_code::text, 2, '0') || '|' ||
        COALESCE(current_offers.canonical_id, current_offers.source_product_id, current_offers.display_name)
    )) AS id,
    current_offers.canonical_id AS product_id,
    source_markets.market_key || ':' || LPAD(cities.plate_code::text, 2, '0') AS market_id,
    source_markets.market_key,
    source_markets.name AS market_name,
    source_markets.segment AS market_type,
    source_markets.coverage_scope,
    source_markets.pricing_scope,
    CASE
        WHEN source_markets.coverage_scope IN ('national_store_network', 'wide_national', 'all_81_target')
            THEN 'national_reference_price'
        ELSE 'local_market_price'
    END AS price_source_type,
    LPAD(cities.plate_code::text, 2, '0') AS city_code,
    cities.name AS city_name,
    current_offers.source_barcode AS barcode,
    COALESCE(current_offers.promo_price, current_offers.listed_price) AS price,
    'TRY'::text AS currency,
    CASE
        WHEN cp.size_value IS NULL OR cp.size_unit IS NULL OR cp.size_value = 0 THEN NULL
        WHEN LOWER(cp.size_unit) IN ('g', 'gr', 'gram') THEN ROUND((COALESCE(current_offers.promo_price, current_offers.listed_price) / (cp.size_value / 1000.0))::numeric, 2)
        WHEN LOWER(cp.size_unit) IN ('kg') THEN ROUND((COALESCE(current_offers.promo_price, current_offers.listed_price) / cp.size_value)::numeric, 2)
        WHEN LOWER(cp.size_unit) IN ('ml') THEN ROUND((COALESCE(current_offers.promo_price, current_offers.listed_price) / (cp.size_value / 1000.0))::numeric, 2)
        WHEN LOWER(cp.size_unit) IN ('cl') THEN ROUND((COALESCE(current_offers.promo_price, current_offers.listed_price) / (cp.size_value / 100.0))::numeric, 2)
        WHEN LOWER(cp.size_unit) IN ('lt', 'l', 'litre', 'liter') THEN ROUND((COALESCE(current_offers.promo_price, current_offers.listed_price) / cp.size_value)::numeric, 2)
        WHEN LOWER(cp.size_unit) IN ('adet', 'ad', 'pcs', 'piece') THEN ROUND((COALESCE(current_offers.promo_price, current_offers.listed_price) / cp.size_value)::numeric, 2)
        ELSE NULL
    END AS unit_price,
    CASE
        WHEN cp.size_value IS NULL OR cp.size_unit IS NULL OR cp.size_value = 0 THEN NULL
        WHEN LOWER(cp.size_unit) IN ('g', 'gr', 'gram', 'kg') THEN 'kg'
        WHEN LOWER(cp.size_unit) IN ('ml', 'cl', 'lt', 'l', 'litre', 'liter') THEN 'l'
        WHEN LOWER(cp.size_unit) IN ('adet', 'ad', 'pcs', 'piece') THEN 'adet'
        ELSE NULL
    END AS unit_price_unit,
    (COALESCE(current_offers.availability, 'in_stock') <> 'out_of_stock') AS in_stock,
    current_offers.image_url,
    current_offers.observed_at::timestamptz AS captured_at,
    current_offers.observed_at::timestamptz AS last_changed_at,
    source_markets.entrypoint_url AS source_url,
    CASE
        WHEN current_offers.source_barcode IS NOT NULL THEN 0.99
        WHEN current_offers.canonical_id IS NOT NULL THEN 0.93
        ELSE 0.75
    END AS source_confidence,
    current_offers.run_id
FROM current_offers
JOIN cities
    ON cities.plate_code = current_offers.city_plate_code
JOIN source_markets
    ON source_markets.market_key = current_offers.market_key
LEFT JOIN canonical_products cp
    ON cp.canonical_id = current_offers.canonical_id;

CREATE VIEW mg_price_history AS
WITH history_base AS (
    SELECT
        md5(
            COALESCE(offers.canonical_id, offers.source_product_id, offers.display_name) || '|' ||
            offers.market_key || '|' ||
            LPAD(cities.plate_code::text, 2, '0') || '|' ||
            offers.observed_at
        ) AS id,
        offers.canonical_id AS product_id,
        source_markets.market_key || ':' || LPAD(cities.plate_code::text, 2, '0') AS market_id,
        COALESCE(cp.primary_barcode, offers.source_barcode) AS barcode,
        LPAD(cities.plate_code::text, 2, '0') AS city_code,
        cities.name AS city_name,
        source_markets.name AS market_name,
        COALESCE(offers.promo_price, offers.listed_price) AS price,
        'TRY'::text AS currency,
        CASE
            WHEN cp.size_value IS NULL OR cp.size_unit IS NULL OR cp.size_value = 0 THEN NULL
            WHEN LOWER(cp.size_unit) IN ('g', 'gr', 'gram') THEN ROUND((COALESCE(offers.promo_price, offers.listed_price) / (cp.size_value / 1000.0))::numeric, 2)
            WHEN LOWER(cp.size_unit) IN ('kg') THEN ROUND((COALESCE(offers.promo_price, offers.listed_price) / cp.size_value)::numeric, 2)
            WHEN LOWER(cp.size_unit) IN ('ml') THEN ROUND((COALESCE(offers.promo_price, offers.listed_price) / (cp.size_value / 1000.0))::numeric, 2)
            WHEN LOWER(cp.size_unit) IN ('cl') THEN ROUND((COALESCE(offers.promo_price, offers.listed_price) / (cp.size_value / 100.0))::numeric, 2)
            WHEN LOWER(cp.size_unit) IN ('lt', 'l', 'litre', 'liter') THEN ROUND((COALESCE(offers.promo_price, offers.listed_price) / cp.size_value)::numeric, 2)
            WHEN LOWER(cp.size_unit) IN ('adet', 'ad', 'pcs', 'piece') THEN ROUND((COALESCE(offers.promo_price, offers.listed_price) / cp.size_value)::numeric, 2)
            ELSE NULL
        END AS unit_price,
        CASE
            WHEN cp.size_value IS NULL OR cp.size_unit IS NULL OR cp.size_value = 0 THEN NULL
            WHEN LOWER(cp.size_unit) IN ('g', 'gr', 'gram', 'kg') THEN 'kg'
            WHEN LOWER(cp.size_unit) IN ('ml', 'cl', 'lt', 'l', 'litre', 'liter') THEN 'l'
            WHEN LOWER(cp.size_unit) IN ('adet', 'ad', 'pcs', 'piece') THEN 'adet'
            ELSE NULL
        END AS unit_price_unit,
        (COALESCE(offers.availability, 'in_stock') <> 'out_of_stock') AS in_stock,
        offers.observed_at::timestamptz AS captured_at,
        offers.run_id AS crawl_run_id,
        COALESCE(offers.canonical_id, offers.source_product_id, offers.display_name) AS entity_key,
        LAG(COALESCE(offers.promo_price, offers.listed_price)) OVER (
            PARTITION BY offers.market_key, offers.city_plate_code, COALESCE(offers.canonical_id, offers.source_product_id, offers.display_name)
            ORDER BY offers.observed_at::timestamptz
        ) AS prev_price,
        LAG(COALESCE(offers.availability, 'in_stock') <> 'out_of_stock') OVER (
            PARTITION BY offers.market_key, offers.city_plate_code, COALESCE(offers.canonical_id, offers.source_product_id, offers.display_name)
            ORDER BY offers.observed_at::timestamptz
        ) AS prev_in_stock,
        COALESCE(offers.promo_price, offers.listed_price) AS active_price
    FROM offers
    JOIN cities
        ON cities.plate_code = offers.city_plate_code
    JOIN source_markets
        ON source_markets.market_key = offers.market_key
    LEFT JOIN canonical_products cp
        ON cp.canonical_id = offers.canonical_id
)
SELECT
    id,
    product_id,
    market_id,
    barcode,
    city_code,
    city_name,
    market_name,
    price,
    currency,
    unit_price,
    unit_price_unit,
    in_stock,
    captured_at,
    crawl_run_id,
    CASE
        WHEN prev_price IS NULL AND prev_in_stock IS NULL THEN 'first_seen'
        WHEN prev_in_stock IS DISTINCT FROM in_stock AND in_stock = FALSE THEN 'out_of_stock'
        WHEN prev_in_stock IS DISTINCT FROM in_stock AND in_stock = TRUE THEN 'restocked'
        WHEN prev_price IS DISTINCT FROM active_price AND active_price > prev_price THEN 'price_increase'
        WHEN prev_price IS DISTINCT FROM active_price AND active_price < prev_price THEN 'price_drop'
        ELSE 'snapshot'
    END AS change_type
FROM history_base;

CREATE MATERIALIZED VIEW mg_product_city_summary AS
WITH current_base AS (
    SELECT
        COALESCE(cp.primary_barcode, mg_market_offers.barcode) AS barcode,
        mg_market_offers.city_code,
        mg_market_offers.city_name,
        mg_market_offers.price,
        mg_market_offers.in_stock,
        mg_market_offers.captured_at
    FROM mg_market_offers
    LEFT JOIN canonical_products cp
        ON cp.canonical_id = mg_market_offers.product_id
    WHERE COALESCE(cp.primary_barcode, mg_market_offers.barcode) IS NOT NULL
),
history_base AS (
    SELECT
        barcode,
        city_code,
        price,
        in_stock,
        captured_at
    FROM mg_price_history
    WHERE barcode IS NOT NULL
),
history_7 AS (
    SELECT
        barcode,
        city_code,
        MAX(CASE WHEN rn_asc = 1 THEN price END) AS first_price,
        MAX(CASE WHEN rn_desc = 1 THEN price END) AS last_price
    FROM (
        SELECT
            barcode,
            city_code,
            price,
            captured_at,
            ROW_NUMBER() OVER (PARTITION BY barcode, city_code ORDER BY captured_at ASC) AS rn_asc,
            ROW_NUMBER() OVER (PARTITION BY barcode, city_code ORDER BY captured_at DESC) AS rn_desc
        FROM history_base
        WHERE captured_at >= NOW() - INTERVAL '7 day'
    ) AS ranked
    GROUP BY barcode, city_code
),
history_30 AS (
    SELECT
        barcode,
        city_code,
        MAX(CASE WHEN rn_asc = 1 THEN price END) AS first_price,
        MAX(CASE WHEN rn_desc = 1 THEN price END) AS last_price
    FROM (
        SELECT
            barcode,
            city_code,
            price,
            captured_at,
            ROW_NUMBER() OVER (PARTITION BY barcode, city_code ORDER BY captured_at ASC) AS rn_asc,
            ROW_NUMBER() OVER (PARTITION BY barcode, city_code ORDER BY captured_at DESC) AS rn_desc
        FROM history_base
        WHERE captured_at >= NOW() - INTERVAL '30 day'
    ) AS ranked
    GROUP BY barcode, city_code
)
SELECT
    barcode,
    city_code,
    city_name,
    COUNT(*) AS offer_count,
    COUNT(*) FILTER (WHERE in_stock) AS in_stock_offer_count,
    ROUND(MIN(price)::numeric, 2) AS lowest_price,
    ROUND(MAX(price)::numeric, 2) AS highest_price,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price)::numeric, 2) AS median_price,
    MAX(captured_at) AS last_seen_at,
    CASE
        WHEN history_7.first_price IS NULL OR history_7.last_price IS NULL THEN NULL
        ELSE ROUND((history_7.last_price - history_7.first_price)::numeric, 2)
    END AS price_change_7d,
    CASE
        WHEN history_30.first_price IS NULL OR history_30.last_price IS NULL THEN NULL
        ELSE ROUND((history_30.last_price - history_30.first_price)::numeric, 2)
    END AS price_change_30d,
    ROUND((COUNT(*) FILTER (WHERE in_stock)::numeric / NULLIF(COUNT(*), 0)), 4) AS availability_ratio,
    CURRENT_TIMESTAMP AS updated_at
FROM current_base
LEFT JOIN history_7
    USING (barcode, city_code)
LEFT JOIN history_30
    USING (barcode, city_code)
GROUP BY
    barcode,
    city_code,
    city_name,
    history_7.first_price,
    history_7.last_price,
    history_30.first_price,
    history_30.last_price;

CREATE MATERIALIZED VIEW mg_product_best_offers AS
WITH ranked AS (
    SELECT
        COALESCE(cp.primary_barcode, mg_market_offers.barcode) AS barcode,
        mg_market_offers.city_code,
        mg_market_offers.city_name,
        mg_market_offers.market_key,
        mg_market_offers.market_name,
        mg_market_offers.market_type,
        mg_market_offers.price_source_type,
        mg_market_offers.price,
        mg_market_offers.unit_price,
        mg_market_offers.currency,
        mg_market_offers.in_stock,
        mg_market_offers.image_url,
        mg_market_offers.captured_at,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(cp.primary_barcode, mg_market_offers.barcode), mg_market_offers.city_code
            ORDER BY mg_market_offers.price ASC NULLS LAST, mg_market_offers.captured_at DESC
        ) AS rank_by_price,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(cp.primary_barcode, mg_market_offers.barcode), mg_market_offers.city_code
            ORDER BY mg_market_offers.unit_price ASC NULLS LAST, mg_market_offers.captured_at DESC
        ) AS rank_by_unit_price
    FROM mg_market_offers
    LEFT JOIN canonical_products cp
        ON cp.canonical_id = mg_market_offers.product_id
    WHERE COALESCE(cp.primary_barcode, mg_market_offers.barcode) IS NOT NULL
)
SELECT *
FROM ranked
WHERE rank_by_price <= 10 OR rank_by_unit_price <= 10;

CREATE MATERIALIZED VIEW mg_product_price_trends AS
WITH history_base AS (
    SELECT
        barcode,
        city_code,
        market_name,
        price,
        in_stock,
        captured_at
    FROM mg_price_history
    WHERE barcode IS NOT NULL
),
history_7 AS (
    SELECT
        barcode,
        city_code,
        MAX(CASE WHEN rn_asc = 1 THEN price END) AS first_price,
        MAX(CASE WHEN rn_desc = 1 THEN price END) AS last_price
    FROM (
        SELECT
            barcode,
            city_code,
            price,
            captured_at,
            ROW_NUMBER() OVER (PARTITION BY barcode, city_code ORDER BY captured_at ASC) AS rn_asc,
            ROW_NUMBER() OVER (PARTITION BY barcode, city_code ORDER BY captured_at DESC) AS rn_desc
        FROM history_base
        WHERE captured_at >= NOW() - INTERVAL '7 day'
    ) AS ranked
    GROUP BY barcode, city_code
),
history_30 AS (
    SELECT
        barcode,
        city_code,
        MAX(CASE WHEN rn_asc = 1 THEN price END) AS first_price,
        MAX(CASE WHEN rn_desc = 1 THEN price END) AS last_price,
        ROUND(AVG(CASE WHEN in_stock THEN 1.0 ELSE 0.0 END)::numeric, 4) AS availability_ratio_30d,
        COUNT(DISTINCT market_name) AS markets_seen_count,
        MAX(captured_at) AS last_seen_at
    FROM (
        SELECT
            barcode,
            city_code,
            market_name,
            price,
            in_stock,
            captured_at,
            ROW_NUMBER() OVER (PARTITION BY barcode, city_code ORDER BY captured_at ASC) AS rn_asc,
            ROW_NUMBER() OVER (PARTITION BY barcode, city_code ORDER BY captured_at DESC) AS rn_desc
        FROM history_base
        WHERE captured_at >= NOW() - INTERVAL '30 day'
    ) AS ranked
    GROUP BY barcode, city_code
)
SELECT
    history_30.barcode,
    history_30.city_code,
    CASE
        WHEN history_7.first_price IS NULL OR history_7.last_price IS NULL THEN NULL
        ELSE ROUND((history_7.last_price - history_7.first_price)::numeric, 2)
    END AS price_change_7d,
    CASE
        WHEN history_30.first_price IS NULL OR history_30.last_price IS NULL THEN NULL
        ELSE ROUND((history_30.last_price - history_30.first_price)::numeric, 2)
    END AS price_change_30d,
    history_30.availability_ratio_30d,
    history_30.markets_seen_count,
    history_30.last_seen_at,
    CURRENT_TIMESTAMP AS updated_at
FROM history_30
LEFT JOIN history_7
    USING (barcode, city_code);

CREATE INDEX IF NOT EXISTS idx_mg_product_city_summary_barcode_city
ON mg_product_city_summary (barcode, city_code);

CREATE INDEX IF NOT EXISTS idx_mg_product_best_offers_barcode_city_price
ON mg_product_best_offers (barcode, city_code, rank_by_price);

CREATE INDEX IF NOT EXISTS idx_mg_product_best_offers_barcode_city_unit
ON mg_product_best_offers (barcode, city_code, rank_by_unit_price);

CREATE INDEX IF NOT EXISTS idx_mg_product_price_trends_barcode_city
ON mg_product_price_trends (barcode, city_code);
