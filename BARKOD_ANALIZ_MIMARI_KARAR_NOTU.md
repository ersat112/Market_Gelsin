Barkod Analiz Icin Mimari Karar Notu
Tarih: 2026-04-01

Bu belge, Barkod Analiz tarafindan paylasilan
`market-gelsin-supabase-firebase-architecture.md`
planinin Market Gelsin tarafindaki mevcut sistemle birlestirilmis nihai karar notudur.

Amac
- Barkod Analiz ekibinin hangi mimariye gore hazirlanacagini netlestirmek
- Supabase, Firebase ve HTTP API rollerini kesinlestirmek
- ilk surumde hangi entegrasyon yolunun esas alinacagini sabitlemek

Nihai Karar

1. Collector kaynak sistem
- Market Gelsin collector ve scraper hattinin operasyonel kaynak sistemi su an kompakt SQLite collector DB'dir.
- Ham crawl, parse ve normalization burada uretilir.
- Bu katman mobil istemciye acilmaz.

2. Supabase rolu
- Supabase, Barkod Analiz icin ana read-model ve servis veritabani olacaktir.
- Yani Barkod Analiz'in okudugu operasyonel fiyat katmani Supabase uzerinden gelecektir.
- Ancak mevcut collector dogrudan Supabase uzerine yazan tek kaynak sisteme henuz cevrilmeyecektir.
- Gecis modeli: `SQLite collector -> Supabase read-model`.

3. Firebase rolu
- Firebase ana fiyat veritabani olmayacak.
- Firebase yalnizca hafif ve turetilmis ayna katmani olacak.
- Bugun aktif olan kisim `scan/signal mirror` katmanidir.
- Fiyat snapshot/trend aynasi gelecek fazda eklenebilir.

4. Barkod Analiz istemci entegrasyonu
- Ilk fazda Barkod Analiz dogrudan HTTP API contract'ina baglanmalidir.
- Firebase fiyat okumasi ilk surumde zorunlu degildir.
- Firebase fiyat mirror'u eklendiginde istemci onu hizli cache/shortcut katmani olarak kullanabilir.

Kabul Edilen Noktalar

- Supabase read-model ve fiyat sorgu katmani olarak kullanilsin
- Firebase mobil tarafta hafif ayna rolu oynasin
- Ham crawl verisi mobil tarafa tasinmasin
- Fiyat gecmisi append-only mantiginda korunsun
- Analytics ozeti ayrica hesaplanabilsin
- Barkod Analiz nihai urun onerme mantiginin sahibi olmaya devam etsin

Revize Edilen Noktalar

1. "Supabase tek source of truth" ifadesi
- Revize: Barkod Analiz ve istemci katmani icin source of truth Supabase read-model olabilir.
- Ama veri toplama ve ham kaynak sistem tarafinda source of truth su an collector DB'dir.
- Bu ayrim operasyonel risk ve maliyet kontrolu icin bilincli olarak korunuyor.

2. Firebase okuma sirasi
- Barkod Analiz planinda "once Firebase, sonra API fallback" onerisi var.
- Revize: V1 icin "once HTTP API" modeli esas alinmali.
- Firebase pricing snapshot/trend mirror'u eklendiginde istemci bunu hizlandirici cache katmani olarak kullanabilir.

3. Firebase pricing mirror kapsamı
- Scan ve signal aynasi bugun aktif.
- `pricing_snapshots`, `pricing_trends`, `pricing_alternatives` aynasi henuz aktif degil.
- Barkod Analiz ekibi bu koleksiyonlari gelecege hazir sekilde tasarlayabilir, ama ilk cikisi buna baglamamali.

Bugunku Sistem Durumu

- `81` il
- `83` aktif market
- `50` canli adapter
- `30` buyuksehir ili `live_controlled_local`
- `25` il `verified_local_needs_adapter`
- `26` il `discovery_pending_national_fallback`
- `3,129,416` `current_offers`
- `3,543,864` tarihsel `offers`
- `14` shared snapshot
- `1,134` shared city run

V1 Kapsam

Ulusal market cekirdegi
- `cepte_sok`
- `a101_kapida`
- `bim_market`
- `migros_sanal_market`
- `tarim_kredi_koop_market`
- `bizim_toptan_online`
- `carrefoursa_online_market`

Buyuksehir yerel dalga
- `30` buyuksehir belediyeli il
- bu illerde mevcut canli yerel market kapsami `city_controlled_flow_plan` uzerinden yonetilir

Kozmetik cekirdegi
- `eveshop_online`
- `tshop_online`
- `flormar_online`
- `gratis_online`
- `rossmann_online`
- `kozmela_online`

Barkod Analiz'in Hedef Almasi Gereken API

Ana contract uclari
- `GET /v1/products/{barcode}/offers`
- `GET /v1/products/{barcode}/price-history`
- `POST /v1/pricing/alternatives`
- `GET /v1/search/products`

Destek uclari
- `GET /api/v1/status`
- `GET /api/v1/program/coverage`
- `GET /api/v1/integrations/status`
- `POST /api/v1/barcode/scans`
- `POST /api/v1/barcode/scans/batch`

Offer payloadinda Barkod Analiz'in dikkate almasi gereken alanlar
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

Kritik semantic alan
- `price_source_type = national_reference_price`
  - ulusal zincir veya ulusal kozmetik zinciri referans fiyati
- `price_source_type = local_market_price`
  - kullanicinin ilindeki yerel market fiyati

Bu ayrim Barkod Analiz tarafinda korunmalidir.
Ulusal referans fiyat ile yerel canli market fiyati ayni kartta gosterilebilir, ama ayni veri turu gibi ele alinmamalidir.

Supabase Read-Model Icın Onerilen `mg_*` Eslestirmesi

Collector tablolari -> Supabase read-model / servis tablolari

- `scrape_runs` -> `mg_crawl_runs`
- `raw_products` -> `mg_raw_products`
- `canonical_products` + `canonical_product_barcodes` -> `mg_products`
- `source_markets` + `cities` + coverage bilgileri -> `mg_markets`
- `current_offers` / `effective_offers` -> `mg_market_offers`
- `offers` -> `mg_price_history`

Ozet / view katmani
- `mg_product_city_summary`
- `mg_product_best_offers`
- `mg_product_price_trends`

Bugunku uygulama durumu
- `mg_*` read-model Supabase uzerinde kurulmustur.
- temel view'lar:
  - `mg_products`
  - `mg_markets`
  - `mg_market_offers`
  - `mg_price_history`
- materialized view'lar:
  - `mg_product_city_summary`
  - `mg_product_best_offers`
  - `mg_product_price_trends`

Not
- Bu `mg_*` isimleri Barkod Analiz tarafinin kavramsal read-modelidir.
- Mevcut migration scriptleri bugun once mevcut SQLite tablo yapisini Supabase'e tasir.
- `mg_*` isimlendirmesi ister view, ister tablo, ister materialized read-model olarak ikinci adimda kurulabilir.

Firebase Icin Nihai Karar

Bugun aktif
- `market_gelsin_barcode_scans/events/items`
- `market_gelsin_barcode_scans/daily_signals/items`

Gelecek pricing mirror koleksiyonlari
- `pricing_snapshots`
- `pricing_trends`
- `pricing_alternatives`

Ancak bunlar V1 cikis blokajı degildir.
Ilk cikista Barkod Analiz fiyat verisini API uzerinden okumaya gore hazirlanmalidir.

Tarama / Hot Refresh Akisi

- Barkod Analiz scan eventlerini `POST /api/v1/barcode/scans` veya batch ucu ile yollar
- API eventleri collector DB'ye yazar
- Eventler opsiyonel olarak Firebase ve Supabase/Postgres tarafina aynalanir
- `barcode_scan_signals` ve `hot_product_refresh_candidates` katmani yeniden kurulur
- Bu sinyaller 48 saatlik hot refresh programini besler

Fazlama

Faz 1
- HTTP API contract entegrasyonu
- Supabase `lean_current` migration
- ulusal marketler + buyuksehir yerel marketler + aktif kozmetik kapsami
- `image_url`, fiyat gecmisi, fiyat tipi ayrimi

Faz 2
- `mg_product_city_summary`
- `mg_product_best_offers`
- `mg_product_price_trends`
- Firebase `pricing_snapshots` / `pricing_trends`

Faz 3
- populer barkodlar icin precomputed `pricing_alternatives`
- district / mahalle ayrimi
- daha guclu yerel market kapsami

Barkod Analiz Ekibinin Simdi Hazirlanmasi Gerekenler

1. istemci entegrasyonunu HTTP API contract'ina gore kurmak
2. `price_source_type` alanini UI ve karar motorunda ayri ele almak
3. Firebase pricing mirror gelmese bile ekranlarin API-first calisacak sekilde yazilmasi
4. scan event flush / retry mekanizmasini `barcode/scans` uclari icin hazirlamak
5. Supabase tablolarina dogrudan mobil sorgu yazmamak; backend/edge/API katmani varsaymak

Kisa Ozet

- Collector kaynak sistem bizde kalir
- Supabase Barkod Analiz icin ana read-model olur
- Firebase sadece hafif mirror olur
- V1 entegrasyon modeli API-first'tur
- Barkod Analiz bu plana gore hazirlanmalidir
