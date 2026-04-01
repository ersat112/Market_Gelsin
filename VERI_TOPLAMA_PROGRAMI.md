Veri Toplama Programi
Tarih: 2026-03-31

Amac
- V1'de Turkiye geneli cekirdek ulusal marketleri ve buyuksehir belediyeli illerdeki yerel zincirleri yayina hazir hale getirmek.
- V2'de kalan illerdeki yerel oyunculari ayni veri modeliyle genisletmek.
- Tum fiyat gecmisini tarih bazli saklayip Barkod Analiz tarafina API ile acmak.

Cadence
- Haftalik full refresh: `168` saat
- Hot product refresh: `48` saat
- History mode: `append_only_offer_snapshots`
- Image capture policy: `required`

V1 Cekirdek Ulusal Marketler
- `cepte_sok`
- `a101_kapida`
- `bim_market`
- `migros_sanal_market`
- `tarim_kredi_koop_market`
- `bizim_toptan_online`
- `carrefoursa_online_market`

V1 Buyuksehir Yerel Dalgasi
- Buyuksehir belediyesi bulunan iller `city_collection_program` tablosunda `v1_metro_local` olarak isaretlenir.
- Bu illerde hedef: ulusal cekirdek + yerel zincirlerin tam katalog / canli adapter kapsami.

V2 Genisleme Dalgasi
- Buyuksehir disindaki iller `v2_remaining_local` olarak isaretlenir.
- Yerel oyuncularin veri muhendisligi, adapter kesfi ve haftalik / hot refresh hattina kademeli baglanmasi hedeflenir.

Veri Tarihcesi
- Tum fiyat snapshotlari `offers.observed_at` ile append-only tutulur.
- `current_offers` son basarili run'i temsil eder.
- Fiyat gecmisi, `GET /v1/products/{barcode}/price-history` ve analytics ozetlerinde kullanilir.

Hot Refresh Mantigi
- Barkod Analiz tarama sinyalleri `barcode_scan_signals` tablosuna akar.
- Bu sinyallerden `hot_product_refresh_candidates` uretilir.
- Adaylar bugunku adapter kabiliyetine gore urun bazli degil, market+il rerun seviyesinde dispatch edilir.

Calistirma
- Program dry-run:
  - `python3 /Users/ersat/Desktop/Market_Gelsin/run_collection_program.py --lane weekly_full --scope v1 --dry-run`
- Haftalik full:
  - `python3 /Users/ersat/Desktop/Market_Gelsin/run_collection_program.py --lane weekly_full --scope all`
- Hot scan:
  - `python3 /Users/ersat/Desktop/Market_Gelsin/run_collection_program.py --lane hot_scan --scope all`

API
- `GET /api/v1/program/coverage`
- `GET /api/v1/status`
- `GET /v1/products/{barcode}/offers`
- `GET /v1/products/{barcode}/price-history`
