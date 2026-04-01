# Ulusal Veri Akisi ve Barkod

Bu dokuman, ulusal market verisini veritabanina nasil yazdigimizi ve barkod eslesmesini hangi sirayla yaptigimizi ozetler.

## Tek komutla toplu ulusal cekim

```bash
python3 /Users/ersat/Desktop/Market_Gelsin/run_all_national_markets.py --city-limit 81 --skip-fresh-hours 0
```

Durum ozeti:

```bash
python3 /Users/ersat/Desktop/Market_Gelsin/report_national_market_status.py
```

CarrefourSA, Migros, Bizim Toptan, Tarim Kredi Koop, Cepte Sok ve GetirBuyuk gibi paylasimli katalog veren ulusal zincirlerde toplu akista seed run alip ayni snapshot'i 81 ile fan-out yaziyoruz. Bu hizlandirma [national_runner.py](/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/national_runner.py) ve [runner.py](/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/runner.py) icine eklendi.
Son iterasyonda yazim hattini da iyilestirdik: run bazli transaction ve seed run'dan toplu SQL clone kullaniyoruz. Boylece ayni urunleri 81 kez yeniden normalize etmek yerine bir kez alip sehirlere daha hizli yayiyoruz.

## Veri hangi tablolara yaziliyor

1. `scrape_runs`
   Her market + il kosusu once burada `running` olarak acilir, sonra `completed`, `completed_with_errors` veya `failed` olur.

2. `raw_products`
   Adapterdan gelen ham urun kaydi burada tutulur. Kaynak urun id, barkod, kategori, isim, fiyat, stok, gorsel ve ham payload burada saklanir.

3. `canonical_products`
   Ham urunler normalize edilerek ortak urun kimligine baglanir. Barkod varsa `bc:{barcode}` kimligi tercih edilir; yoksa normalize isim parmak izi kullanilir.

4. `canonical_product_barcodes`
   Guvenilir barkodlar canonical urune eklenir. Boylece ayni barkod farkli marketlerde tekrar geldiginde ayni urune oturur.

5. `offers`
   Marketin son okunabilir teklif katmani buradadir. API ve karsilastirma mantigi esas olarak bu tabloyu kullanir.

6. `current_offers`
   Bu bir tablo degil, view'dur. Her market + il icin son basarili run'i secerek guncel fiyat katmanini verir. Tekrarlanan batch kosularinda tarihce `offers`ta kalir, guncel okuma `current_offers`tan yapilir.

## Barkod eslesmesi nasil yapiliyor

Runner su sirayla barkod cikarir:

1. Adapterin dogrudan verdigi `source_barcode`
2. `payload_json` icindeki barkod benzeri alanlar
3. Kaynak urun id barkod formatindaysa o deger
4. Urun adi, marka veya boyut alanlarindan cikabilen guclu barkod adayi

Not:
Kaynak urun id yalnizca `12/13/14` haneli ve checksum'u gecerli GTIN gorunumundeyse barkod sayilir. Kisa sayisal storefront id'leri barkod yerine SKU olarak kalir.

Sonra:

1. Barkod normalize edilir.
2. Varsa canonical urun `bc:{barcode}` kimligiyle baglanir.
3. Barkod `canonical_product_barcodes` tablosuna yazilir.
4. Teklif kaydi ayni barkodla `offers.source_barcode` alanina yazilir.

## Kod akisi

- Run acma ve kapama: [/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/runner.py](/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/runner.py)
- Paylasimli katalog fan-out batch'i: [/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/national_runner.py](/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/national_runner.py)
- Barkod cikarma: [/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/runner.py](/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/runner.py)
- Isim ve barkod normalizasyonu: [/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/normalization.py](/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/normalization.py)
- Veritabani semasi: [/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/schema.sql](/Users/ersat/Desktop/Market_Gelsin/nationwide_platform/schema.sql)

## Ulusal marketlerde mevcut durum

- Canli veri yazanlar: `BIM`, `A101`, `Cepte Sok`, `Migros`, `CarrefourSA`, `Tarim Kredi Koop`, `Bizim Toptan`, `GetirBuyuk`
- Planli ama henuz canli olmayanlar: yok

## A101 notu

`A101 Kapida` su anda resmi `https://a101.wawlabs.com/search?q=*` JSON yuzeyi uzerinden akiyor.
Bu katman 81 il icin kontrollu ulusal katalog verisini DB'ye yaziyor.
Adres-duyarli daha derin varyasyon katmani sonraki iterasyonda ayri session/adres cozumlemesi ile eklenecek.

## CarrefourSA notu

`CarrefourSA` su anda `cloudscraper` ile acilan resmi web katalogu uzerinden, `/search?q=:relevance:productPrimaryCategoryCode:{code}` akisiyla taraniyor.
Tek market fetch'i Ankara seed'i ile aliniyor ve ayni katalog snapshot'i 81 ile yaziliyor.
Bu asamada `current_offers` icinde `81` ilde `121500` guncel teklif var; barkod alani henuz acik katalogda gelmedigi icin `0`.

## Migros notu

`Migros` REST katalog akisi su anda `sku` uzerinden geliyor. Son payload'larda guvenilir barkod alani gorunmedigi icin bu zincirde barkod kolonunu bos birakiyoruz; boylece 14 haneli urun id'leri yanlis barkod olarak yazilmiyor.

## GetirBuyuk notu

`GetirBuyuk` su anda resmi `https://getir.com/buyuk/kategori/...` SSR kategori sayfalari uzerinden akiyor. Ana kategori sayfalarinin `__NEXT_DATA__` state'i, alt kategori gruplari ve urun listelerini gomulu olarak veriyor.
Bu akista `81` ilde `671814` guncel teklif yazildi. Acik state katmaninda guvenilir barkod alani gormedigimiz icin barkod kolonu bu markette de su an bos.

## Cepte Sok notu

`Cepte Sok` su anda anasayfa + kampanya grup sayfalari + sinirli kategori sitemap listing akisiyla calisiyor.
Bu genisletme ile `81` ilde `12150` guncel teklif seviyesine ciktik.
Bu halen tam katalog degil; sonraki kalite adimi daha derin kategori/Next.js katmanina gecmek.

## Tarim Kredi Koop notu

`Tarim Kredi Koop` artik sabit 5 kategori yerine kok kategori ve sayfalama kesfiyle akiyor.
Mevcut seed run `3050` urun veriyor ve fan-out sonrasi `81` ilde `247050` guncel teklif yaziyor.

## Bizim Toptan notu

`Bizim Toptan` arama sorgusu ornekleminden cikarildi; kok kategori + `pagenumber` sayfalama akisi uzerinden HTML urun kartlari parse ediliyor.
Mevcut seed run `1728` urun veriyor ve fan-out sonrasi `81` ilde `139968` guncel teklif yaziyor.

Buradaki hedef once tum ulusal zincirleri `offers` tablosuna duzenli akitir hale getirmek, sonra tam katalog ve adres-duyarli varyasyon derinligine gecmek.
