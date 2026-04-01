Supabase Barkod API Plani
Tarih: 2026-04-01

Amac
- Barkod Analiz uygulamasinin fiyat / bulunabilirlik katmanini Supabase ustunde netlestirmek
- Veri toplama hattini ayri, API read-modelini ayri tutmak
- V1'de cekirdek ulusal marketler + buyuksehir yerel zincirleri yayina hazir hale getirmek

Bugunku Seviye
- `83` aktif market
- `50` canli adapter
- `30` buyuksehir ili `live_controlled_local`
- `25` il `verified_local_needs_adapter`
- `26` il `discovery_pending_national_fallback`
- `3,129,416` `current_offers`
- `3,543,864` tarihsel `offers`
- `1,442` il-market hedefi
- `65` yerel market adayi
- `14` `shared_catalog_snapshots`
- `1,134` `shared_catalog_city_runs`

V1 Kapsam
- cekirdek ulusal marketler:
  - `cepte_sok`
  - `a101_kapida`
  - `bim_market`
  - `migros_sanal_market`
  - `tarim_kredi_koop_market`
  - `bizim_toptan_online`
  - `carrefoursa_online_market`
- buyuksehir yerel dalga:
  - `30` buyuksehir belediyeli il
  - bugun canli yerel akisi olan iller `city_controlled_flow_plan.rollout_stage = live_controlled_local`
- kozmetik aktif ulusal zincirleri:
  - `eveshop_online`
  - `tshop_online`
  - `flormar_online`
  - `gratis_online`
  - `rossmann_online`
  - `kozmela_online`

Supabase Mimarisi

1. Collector katmani
- mevcut Python scraper / adapter hatlari lokal veya worker ortaminda calisir
- SQLite collector DB kaynak sistem olmaya devam eder
- veri kaynagi, parse ve normalizasyon burada kalir

2. Supabase Postgres read-model
- Barkod Analiz'in okuyacagi hizli katman Supabase/Postgres olur
- sadece canli subset ve gerekli referans tablolar tasinir
- migration script'i zaten hazir:
  - `/Users/ersat/Desktop/Market_Gelsin/scripts/check_supabase_connection.py`
  - `/Users/ersat/Desktop/Market_Gelsin/scripts/migrate_live_subset_to_postgres.py`
  - `/Users/ersat/Desktop/Market_Gelsin/scripts/migrate_sqlite_to_postgres.py`

3. API katmani
- Barkod Analiz dogrudan crawler DB'ye degil API'ye baglanir
- ilk fazda Python API Supabase veya SQLite runtime ustunden ayni contract'i doner
- daha sonra istersek ayni contract'i Supabase Edge Function veya ayri backend'e tasiyabiliriz

4. Scan telemetry
- Barkod Analiz tarama olaylari `barcode_scan_events` ve `barcode_scan_signals` katmanina akar
- hot refresh mantigi Supabase tarafinda da korunur
- scan ingest yazma isi uygulama istemcisinden degil, API veya guvenli servis uzerinden yapilir

Supabase'e Tasinacak Katman

Tam tasinacak referans tablolar
- `cities`
- `source_markets`
- `market_city_targets`
- `city_collection_program`
- `market_refresh_policy`
- `canonical_products`
- `canonical_product_barcodes`
- `city_local_discovery_tasks`
- `city_local_discovery_queries`
- `city_local_coverage_status`
- `city_controlled_flow_plan`
- `market_adapter_readiness`
- `adapter_onboarding_backlog`
- `barcode_scan_signals`
- `barcode_scan_events`
- `hot_product_refresh_candidates`
- `local_market_candidates`
- `market_storefront_probes`

Canli subset olarak tasinacak tablolar
- `scrape_runs`
- `offers`
- `raw_products`
- `shared_catalog_snapshots`
- `shared_catalog_snapshot_items`
- `shared_catalog_city_runs`

Postgres runtime gorunumleri
- `effective_offers`
- `current_offers`

Uygulanan Barkod read-model katmani
- SQL dosyasi:
  - `/Users/ersat/Desktop/Market_Gelsin/supabase_mg_read_model.sql`
- uygulama script'i:
  - `/Users/ersat/Desktop/Market_Gelsin/scripts/apply_supabase_barkod_read_model.py`
- olusan view'lar:
  - `mg_products`
  - `mg_markets`
  - `mg_market_offers`
  - `mg_price_history`
- olusan materialized view'lar:
  - `mg_product_city_summary`
  - `mg_product_best_offers`
  - `mg_product_price_trends`

Bugunku sayim
- `mg_products`: `37,192`
- `mg_markets`: `1,442`
- `mg_market_offers`: `3,129,416`
- `mg_price_history`: `3,218`
- `mg_product_city_summary`: `1,104,747`
- `mg_product_best_offers`: `1,229,932`
- `mg_product_price_trends`: `118`

API Contract Kararlari

Offer seviyesinde dondurulecek ana alanlar
- `market_key`
- `market_name`
- `market_type`
- `coverage_scope`
- `pricing_scope`
- `price_source_type`
- `price`
- `currency`
- `unit_price`
- `unit_price_unit`
- `in_stock`
- `image_url`
- `captured_at`
- `source_url`
- `source_confidence`

`price_source_type` kurali
- `national_reference_price`: ulusal zincir veya ulusal kozmetik zinciri referans fiyatlari
- `local_market_price`: kullanicinin ilindeki yerel zincir market fiyati

Bu ayrim neden gerekli
- Barkod Analiz ayni listede ulusal zincir referans fiyatini ve yerel market fiyatini gosterebilir
- ama kullaniciya bunlarin ayni sey oldugu yanlis izlenimi verilmez
- gelecekte gercek raf verisi gelirse ucuncu tip eklemek kolay olur

Barkod Analiz Icinde Onerilen Kullanım
- kart 1: en dusuk `local_market_price`
- kart 2: en yakin `national_reference_price`
- kart 3: market sayisi + son veri tazeligi
- fiyat karsilastirma sayfasinda `coverage_scope` ve `pricing_scope` gizli analitik alan olarak tutulabilir

Supabase Kurulum Sirasi

1. baglanti testi
- `python3 /Users/ersat/Desktop/Market_Gelsin/scripts/check_supabase_connection.py`
- DSN'i lokal dosyaya koymak istersen: `/Users/ersat/Desktop/Market_Gelsin/.env.supabase.local`

2. dry-run migration
- `MARKET_GELSIN_MIGRATION_DRY_RUN=1 python3 /Users/ersat/Desktop/Market_Gelsin/scripts/migrate_live_subset_to_postgres.py`

3. canli subset migration
- `MARKET_GELSIN_MIGRATION_PROFILE=lean_current python3 /Users/ersat/Desktop/Market_Gelsin/scripts/migrate_live_subset_to_postgres.py`

4. API sunucusunu Supabase DSN ile kaldirma
- `MARKET_GELSIN_DB_URL=... python3 /Users/ersat/Desktop/Market_Gelsin/api_server.py`

Supabase Guvenlik Modeli
- mobil istemci `anon` key ile fiyat tablolarina dogrudan erismemeli
- Barkod Analiz, backend/edge function uzerinden bu API contract'ini tuketmeli
- `barcode/scans` yazma uclari token veya servis rolu ile korunmali
- ham `raw_products` tablosu istemciye acilmamali

V1 Yayina Hazir Tanimi
- `7` cekirdek ulusal market
- `30` buyuksehir ili
- bu illerde canli yerel zincir marketlerin mevcut kapsami
- fiyat gecmisi
- `image_url`
- Barkod Analiz contract uclari

V2 Genisleme
- `51` ilde kalan yerel oyuncular
- yeni adapter aileleri
- daha guclu barkod kapsami
- analytics ozetlerini materialized read model'e tasima

Bugun icin en dogru yol
- collector SQLite + compacted history modeli korunur
- Supabase yalnizca read-model ve istemci entegrasyon katmani olur
- Barkod Analiz once bu V1 contract'a baglanir
