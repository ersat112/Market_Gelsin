PostgreSQL Gecis Plani
Tarih: 2026-04-01

Hedef mimari
1. Supabase PostgreSQL ana veri tabani olacak.
2. Python API bulutta bu PostgreSQL'e baglanacak.
3. Barkod Analiz mobil app yalnizca HTTP API'ye gidecek.
4. Firebase sadece hafif signal / scan mirror katmani olarak kalacak.

Bugunku Durum
- Ana collector DB kompaktlandi ve boyut yaklasik `7.0 GB`.
- API su an ayakta ve varsayilan olarak SQLite runtime ile cevap veriyor.
- Firebase scan mirror aktif ve dogrulandi.
- Supabase gecisi icin kalan ana eksik, gecerli `MARKET_GELSIN_DB_URL` / `SUPABASE_DB_URL` tanimi.
- Canli snapshot:
  - `81` il
  - `83` aktif market
  - `50` canli adapter
  - `3,129,416` `current_offers`
  - `3,543,864` tarihsel `offers`

Sira
1. Supabase baglantisini dogrula
   `python /Users/ersat/Desktop/Market_Gelsin/scripts/check_supabase_connection.py`
2. Canli prod subset boyutunu olc
   `python /Users/ersat/Desktop/Market_Gelsin/scripts/estimate_live_subset.py`
3. Lean current dry-run al
   `MARKET_GELSIN_MIGRATION_PROFILE=lean_current MARKET_GELSIN_MIGRATION_DRY_RUN=1 python /Users/ersat/Desktop/Market_Gelsin/scripts/migrate_live_subset_to_postgres.py`
4. Lean current subset'i migrate et
   `MARKET_GELSIN_MIGRATION_PROFILE=lean_current python /Users/ersat/Desktop/Market_Gelsin/scripts/migrate_live_subset_to_postgres.py`
5. API'yi PostgreSQL ile ac
   `./scripts/start_market_api.sh`
6. Status ve ornek query ile dogrula
   `/health`
   `/api/v1/status`
   `/v1/products/{barcode}/offers`
7. Gerektiginde full collector gecisi kullan
   `MARKET_GELSIN_MIGRATION_PROFILE=full_history python /Users/ersat/Desktop/Market_Gelsin/scripts/migrate_live_subset_to_postgres.py`
8. Full collector migration sonrasi `mg_*` read-model refresh et
   `python /Users/ersat/Desktop/Market_Gelsin/scripts/apply_supabase_barkod_read_model.py`

Env Yukleme
- Scriptler artik su lokal env dosyalarini otomatik yukler:
  - `/Users/ersat/Desktop/Market_Gelsin/.env.market_gelsin_api.local`
  - `/Users/ersat/Desktop/Market_Gelsin/.env.supabase.local`
  - `/Users/ersat/Desktop/Market_Gelsin/.env.firebase.local`
- Supabase icin pratik kurulum:
  - `/Users/ersat/Desktop/Market_Gelsin/.env.supabase.local`
  - icerik:
    `MARKET_GELSIN_DB_URL=postgresql://...`

Onemli not
- Mevcut ana DB kompaktlandi; buna ragmen Supabase'e ilk geciste full yerine `lean_current` subset ile baslamak en dogru yol.
- Ilk adimda API kodu env verilirse PostgreSQL'e, verilmezse SQLite'a baglanacak sekilde hazirlandi.
- Firebase'e fiyat DB tasinmaz; yalnizca scan / signal verisi gider.
- `lean_current` profilinde `raw_products` tablo semasi korunur ama veri kopyalanmaz; ilk canli geciste sadece current fiyat omurgasi tasinir.
- `full_history` profili tum tablolari, tum `offers` tarihcesini ve tum `raw_products` kayitlarini Supabase'e tasir.
- `full_history` daha yavas ama read-model ve tarihsel fiyat analizi icin tam kapsama verir.

Bugun Icin Son Durum
- Firebase aynasi calisiyor.
- API ayakta.
- Supabase migration scriptleri hazir.
- Supabase `lean_current` migration tamamlandi.
- Barkod Analiz icin `mg_*` read-model katmani kuruldu.
