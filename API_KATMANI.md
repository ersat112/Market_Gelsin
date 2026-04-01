API Katmani
Tarih: 2026-03-28

Amac
- 81 il kapsama planini tek JSON servis uzerinden dis sistemlere acmak
- Market, sehir, teklif, barkod ve sepet karsilastirma sorgularini DB ustunden sunmak
- Mobil uygulamaya gecmeden once veri tabani ve servis katmanini stabilize etmek

Calistirma
- Sunucu: `python3 /Users/ersat/Desktop/Market_Gelsin/api_server.py`
- Python 3.11 baslatma scripti: `/Users/ersat/Desktop/Market_Gelsin/scripts/start_market_api.sh`
- Ornek env dosyasi: `/Users/ersat/Desktop/Market_Gelsin/.env.market_gelsin_api.example`
- Opsiyonel lokal env dosyalari: `/Users/ersat/Desktop/Market_Gelsin/.env.market_gelsin_api.local`, `/Users/ersat/Desktop/Market_Gelsin/.env.supabase.local`, `/Users/ersat/Desktop/Market_Gelsin/.env.firebase.local`
- Varsayilan adres: `http://127.0.0.1:8040`

Uclar
- `GET /v1/products/{barcode}/offers`
- `GET /v1/products/{barcode}/price-history`
- `POST /v1/pricing/alternatives`
- `GET /v1/search/products`
- `GET /health`
- `GET /api/v1/status`
- `GET /api/v1/program/coverage`
- `GET /api/v1/integrations/status`
- `GET /api/v1/barcode/scans/status`
- `GET /api/v1/cities`
- `GET /api/v1/cities/{city_slug}/markets`
- `GET /api/v1/offers?city={city_slug}&q={arama}&market_key={market_key}&barcode={barcode}&limit={n}`
- `GET /api/v1/barcode/{barcode}`
- `POST /api/v1/barcode/scans`
- `POST /api/v1/barcode/scans/batch`
- `POST /api/v1/basket/compare`

Ornekler
- `curl -s "http://127.0.0.1:8040/v1/products/8692971473826/offers?city_code=72&limit=5"`
- `curl -s "http://127.0.0.1:8040/v1/products/8692971473826/price-history?city_code=72&days=30"`
- `curl -s "http://127.0.0.1:8040/v1/search/products?q=domates&city_code=35&limit=5"`
- `curl -s -X POST http://127.0.0.1:8040/v1/pricing/alternatives -H "Content-Type: application/json" -d "{\"city_code\":\"35\",\"barcode\":\"8681771360016\",\"candidate_barcodes\":[\"8681771360016\"]}"`
- `curl -s http://127.0.0.1:8040/api/v1/status`
- `curl -s http://127.0.0.1:8040/api/v1/program/coverage`
- `curl -s http://127.0.0.1:8040/api/v1/integrations/status`
- `curl -s "http://127.0.0.1:8040/api/v1/cities/izmir/markets"`
- `curl -s "http://127.0.0.1:8040/api/v1/offers?city=izmir&q=domates&limit=5"`
- `curl -s http://127.0.0.1:8040/api/v1/barcode/8692971473826`
- `curl -s -X POST http://127.0.0.1:8040/api/v1/barcode/scans -H "Content-Type: application/json" -d "{\"barcode\":\"8690000000001\",\"city_code\":\"34\",\"scanned_at\":\"2026-04-01T10:15:00Z\",\"device_id\":\"android-01\"}"`
- `curl -s -X POST http://127.0.0.1:8040/api/v1/barcode/scans/batch -H "Content-Type: application/json" -d "{\"events\":[{\"barcode\":\"8690000000001\",\"city_code\":\"34\"},{\"barcode\":\"8690000000002\",\"city_code\":\"06\",\"scan_count\":2}],\"rebuild_hot_refresh\":true}"`
- `curl -s -X POST http://127.0.0.1:8040/api/v1/basket/compare -H "Content-Type: application/json" -d "{\"city_slug\":\"izmir\",\"items\":[\"domates\",\"makarna\",\"süt\"]}"`

Sepet karsilastirma govdesi
```json
{
  "city_slug": "izmir",
  "items": ["domates", "makarna", "sut"],
  "min_score": 0.35
}
```

Notlar
- `v1` uclari Barkod Analiz sozlesmesine hizali yeni servis yuzeyidir.
- `v1` offer payload'lari artik `market_key`, `coverage_scope`, `pricing_scope`, `price_source_type` ve `image_url` da tasir.
- `price_source_type` ilk fazda iki deger doner: `national_reference_price` ve `local_market_price`.
- detayli eslesme notlari icin `BARKOD_ANALIZ_ENTEGRASYONU.md` dosyasina bak.
- Supabase gecis modeli ve tasinacak read-model icin `SUPABASE_BARKOD_API_PLANI.md` dosyasina bak.
- `barcode/scans` uclari Barkod Analiz veya benzeri istemcilerden gelen tarama sinyallerini alir, ham event loguna yazar, `barcode_scan_signals` gunluk agregasyonunu artirir ve `hot_product_refresh_candidates` kuyru gunu yeniden kurar.
- `integrations/status` ucu lokal SQLite sayaclarini ve opsiyonel `PostgreSQL` / `Firebase` aynalama durumunu dondurur.
- `program/coverage` ucu v1 cekirdek ulusal marketler, buyuksehir yerel kapsam dalgasi ve v2 genisleme planini doner.
- `cities` ucu rollout ve coverage tablolari ile zenginlestirilmis sehir listesini doner.
- `cities/{city_slug}/markets` ucu ilgili ildeki canli ve planli marketleri, adapter durumunu ve son offer sayisini doner.
- `offers` ucu her markette son gozlenen uniq teklifleri doner.
- Barkod varsa once barkod, yoksa isim/olcu bazli eslesme kullanilir.
- `current_offers` ve `v1` Barkod Analiz cevaplari artik `image_url` tasir.
- `MARKET_GELSIN_INGEST_TOKEN` tanimliysa ingest uclari `Authorization: Bearer <token>` veya `X-API-Key` ister.
- `MARKET_GELSIN_POSTGRES_DSN` varsa kabul edilen scan eventleri PostgreSQL tarafina da yazilir.
- `MARKET_GELSIN_FIREBASE_CREDENTIALS`, `MARKET_GELSIN_FIREBASE_PROJECT_ID`, `MARKET_GELSIN_FIREBASE_COLLECTION` ile Firebase aynalama acilabilir.
- Firebase veri siniri icin `FIREBASE_VERI_STRATEJISI.md` dosyasina bak; mevcut 14 GB fiyat DB'si Firestore'a kopyalanmaz.
- Ana API halen Python standard library ile calisir; PostgreSQL ve Firebase aynalama katmani opsiyonel bagimlilik ister.
