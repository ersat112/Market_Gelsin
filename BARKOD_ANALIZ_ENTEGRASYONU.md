# Barkod Analiz Entegrasyonu

Tarih: 2026-03-31

Bu belge, `/Users/ersat/Desktop/app-barkod-analiz-v1/docs/market-gelsin-api-contract.md`
icindeki API sozlesmesini bu repodaki mevcut veri modeliyle nasil eslestirdigimizi
ozetler.

## Veri Katmani Eslesmesi

Raw Crawl Layer:
- `scrape_runs`
- `raw_products`

Normalized Price Layer:
- `offers`
- `current_offers`
- `canonical_products`
- `canonical_product_barcodes`
- `cities`
- `source_markets`

Analytics Layer:
- su an fiziksel tablo yerine API seviyesinde on-demand hesap
- ozet alanlar `api_service.py` icinde `offers/current_offers` ustunden turetiliyor

## Yeni Barkod Analiz Uclari

- `GET /v1/products/{barcode}/offers`
- `GET /v1/products/{barcode}/price-history`
- `POST /v1/pricing/alternatives`
- `GET /v1/search/products`
- `POST /api/v1/barcode/scans`
- `POST /api/v1/barcode/scans/batch`
- `GET /api/v1/integrations/status`

Bu uclar mevcut `/api/v1/...` uclarini bozmaz. Barkod Analiz icin ayrica ve
sozlesmeye uyumlu olarak acildi.

## Tarama Sinyali Akisi

Barkod Analiz artik fiyat okumak disinda tarama sinyali da yollayabilir.

Yeni ingest akisi:

1. Barkod Analiz `POST /api/v1/barcode/scans` veya batch ucu ile scan event yollar.
2. Sunucu ham event'i `barcode_scan_events` tablosuna yazar.
3. Ayni event gunluk agregasyon olarak `barcode_scan_signals` tablosuna eklenir.
4. Ardindan `hot_product_refresh_candidates` yeniden hesaplanir.
5. Ortam degiskeni varsa ayni eventler opsiyonel olarak PostgreSQL ve Firebase tarafina da aynalanir.

Single event ornek govde:

```json
{
  "barcode": "8690000000001",
  "city_code": "34",
  "scanned_at": "2026-04-01T10:15:00Z",
  "scan_count": 1,
  "device_id": "android-01",
  "session_id": "session-abc"
}
```

Batch ornek govde:

```json
{
  "events": [
    {
      "barcode": "8690000000001",
      "city_code": "34"
    },
    {
      "barcode": "8690000000002",
      "city_code": "06",
      "scan_count": 2
    }
  ],
  "rebuild_hot_refresh": true
}
```

Not:
- `MARKET_GELSIN_INGEST_TOKEN` varsa ingest uclari bearer token ister.
- `event_id` gelmezse sunucu tutarli bir hash uretir ve tekrar gonderilen ayni event'i duplicate sayar.
- Firebase aynalama yalnizca scan eventleri ve gunluk signal ozetleri icindir; mevcut fiyat DB'sinin tamami Firestore'a tasinmaz.

## Ortak Response Alani

Tum yeni `v1` uclari su alanlari dondurur:

- `fetched_at`
- `request_id`
- `data_freshness`
- `partial`
- `warnings`

`data_freshness` su an:
- `mode=weekly_full_plus_hot_scan`
- `last_full_refresh_at`: tam kapsama setinin son basarili refresh tabani
- `last_hot_refresh_at`: en son basarili hot veya normal refresh zamani
- `full_refresh_hours=168`
- `hot_refresh_hours=48`
- `history_mode=append_only_offer_snapshots`

## Alan Eslesmesi

Sozlesmedeki zorunlu alanlarin mevcut karsiligi:

- `barcode` -> `source_barcode` veya `canonical_product_barcodes.barcode`
- `market_name` -> `source_markets.name`
- `city_name` -> `cities.name`
- `price` -> `COALESCE(promo_price, listed_price)`
- `currency` -> sabit `TRY`
- `in_stock` -> `availability != out_of_stock`
- `captured_at` -> `observed_at`
- `source_url` -> once `raw_products.payload_json`, yoksa `source_markets.entrypoint_url`

Ikincil alanlar:

- `unit_price` / `unit_price_unit` -> `canonical_products.size_value/size_unit` uzerinden turetilir
- `normalized_category` -> `canonical_products.category_l1`
- `brand` -> `canonical_products.brand`
- `source_confidence` -> barkod eslesmesi + source URL kalitesine gore API katmaninda turetilir
- `price_change_7d` / `price_change_30d` -> `offers` tarihcesinden on-demand hesaplanir
- `image_url` -> `current_offers.image_url` veya `raw_products.image_url`
- `price_source_type` -> `national_reference_price` veya `local_market_price`
- `pricing_scope` -> `source_markets.pricing_scope`
- `coverage_scope` -> `source_markets.coverage_scope`

## Bugunku Durum

Mevcut barkod kapsami:
- `629` canonical barcode
- `7594` historical offer satirinda barkod
- `510` current offer satirinda barkod

Bu yuzden Barkod Analiz entegrasyonunda en guclu ilk faz:
- barkodlu urun fiyatlari
- barkod bazli fiyat gecmisi
- alternatif barkodlarin ozet fiyat karsilastirmasi
- image_url ile liste ve detay zenginlestirmesi

## Bilinen Sinirlar

- `district` su an kabul edilir ama filtre uygulanmaz; API `warning` doner
- tum marketlerde barkod yok; bazi marketler sadece isim/fingerprint katmaninda
- `source_url` her zaman urun detay sayfasi olmayabilir; fallback olarak market entrypoint kullanilabilir
- analytics ozetleri su an materialized tablo degil, API aninda hesaplar

## Sonraki Teknik Adim

1. barkod tasiyan market adapter oranini yukari cekmek
2. `analytics` katmani icin materialized ozet tablo eklemek
3. Supabase/PostgreSQL tarafinda fiyat / analytics read modeli olusturmak
4. district / mahalle ayrimini adres bazli marketlerde normalize etmek
5. Barkod Analiz istemcisinde otomatik batch flush ve retry stratejisini acmak
