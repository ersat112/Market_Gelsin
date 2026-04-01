# Turkiye Geneli Market Veri Muhendisligi

## Problem Tanimi

Bu urunun asil degeri, kullanicinin bulundugu il ve adres baglaminda online market fiyatlarini karsilastirabilmesidir.
Buradaki zor kisim sadece "urunleri cekmek" degil, su dort problemi birlikte cozebilmektir:

1. Ayni markette fiyatlar adres, magaza ve teslimat bolgesine gore degisebilir.
2. Ayni urun farkli marketlerde farkli ad, gramaj ve kampanya diliyle gelir.
3. Buyuk oyuncularin bir kismi web sayfasinda, bir kismi uygulama/JSON katmaninda veri sunar.
4. Turkiye genelinde 81 il ve binlerce ilce oldugu icin tarama maliyeti ve veri tazeligi dogru planlanmalidir.

Bu nedenle sistem sadece scraper degil, adres-duyarli bir fiyat veri platformu olarak kurgulanmalidir.

## 28 Mart 2026 Itibariyla Dogrulanan Kaynak Gozlemleri

Asagidaki resmi kaynaklar, fiyat ve stok bilgisinin cogu buyuk oyuncuda adres veya teslimat bolgesine gore degistigini gosteriyor:

- CarrefourSA resmi siparis sayfasi, bolgeye ozel fiyat ve teslimat secenekleri icin sehir, ilce ve mahalle girilmesini istiyor.
- CarrefourSA kurumsal sayfasi, online marketin farkli siparis ve teslimat secenekleriyle adres teslim yaptigini acikca anlatiyor.
- Migros resmi kampanya sayfasi, kampanyanin belirli magazalara ozel oldugunu ve farkli illerde farkli magazalarin gecerli oldugunu listeliyor.
- Cepte Sok urun sayfalari, stok ve fiyat bilgisinin satis noktasi ve musteri adresine gore degisebildigini soyluyor.
- Getir SSS sayfasi, kullanilabilen hizmetlerin ve kapsamin adrese gore degisebildigini ve 81 ilin hedef oldugunu belirtiyor.
- A101 kurumsal raporu, 81 ilde faaliyet gosterdigini; web ve mobil uzerinden market urunu teslimati sundugunu belirtiyor. A101 urun sayfalarinda da kanal bazli fiyat farki oldugu ifade ediliyor.

Bu nedenle veri modeli "il bazli" baslamali ama "adres-duyarli" calisacak sekilde tasarlanmalidir.

Onemli not:

- Sisteme bir marketi eklemek, o marketi her ilde "kesin aktif" saymak anlamina gelmez.
- Veri modeli uc ayri durumu tasir:
  - `all_cities_probe`: 81 ilde probe edilmesi gereken ulusal oyuncu
  - `explicit_city_list`: belirli illerde kesin bilinen oyuncu
  - `discovery_backlog`: sisteme alinmis ama il listesi netlestirilmesi gereken oyuncu

## Sistem Hedefi

Hedef mimari:

- 81 il icin market kapsama kaydi tutmak
- Buyuk oyuncular icin il bazli tarama backlog'u olusturmak
- Adres gerektiren kaynaklarda sehir merkezi ve secili ilce/mahalle anchor adresleriyle probe yapmak
- Ham urun verisini normalize edip ortak kataloga baglamak
- Mobil uygulamaya sehir, market, urun ve alisveris listesi bazli servis vermek

## Oncelikli Ulusal Oyuncular

P0 onboarding sirasinda sisteme alinacak buyuk oyuncular:

- Migros Sanal Market
- CarrefourSA Online Market
- A101 Kapida
- Cepte Sok
- GetirBuyuk
- Macroonline

P0.5 ile ayni mimariye alinacak yerel/bolgesel oyuncular:

- Mismar Online / Konya
- Yunus Market Online / Ankara
- Sehzade Online / Kayseri

P1 sonrasi degerlendirilecek genisletmeler:

- Yemeksepeti Market
- istegelsin benzeri adres bazli oyuncular
- guclu bolgesel market zincirleri

## Mimarinin Ana Ilkeleri

### 1. Il bazli degil, il + teslimat bolgesi bazli dusun

Uygulama kullaniciya "Konya fiyatlari" gosteriyor gibi gorunebilir; fakat veri toplama katmaninda asagidaki katmanlar ayrilmalidir:

- il
- ilce
- mahalle
- kaynak magazasi veya dark store
- teslimat slotu

Il bazli ilk görünum urun tarafinda korunur; ancak veri toplama tarafinda minimum bir "probe address" kavrami zorunludur.

### 2. Ham veri ile kanonik katalog ayri tutulmali

Ham veri:

- kaynak markette gorunen urun adi
- kampanya dili
- ham kategori
- ham fiyat
- ham stok durumu
- goruntu URL'si
- ham JSON veya HTML payload'i

Kanonik veri:

- normalize urun adi
- marka
- gramaj/hacim/adet
- kategori seviyesi
- eslenmis urun kimligi

### 3. Tarama planlayici merkezi olmali

Her market kendi scriptiyle gelistirilmemeli.
Tek bir planlayici:

- hangi ilde hangi marketin ne zaman taranacagini
- hangi kaynakta adres gerektiğini
- hangi markette sitemap veya kategori tabanli tarama yapilacagini
- ne kadar sıklıkla yenilenecegini

tek yerden yonetmelidir.

### 4. Veri kalitesi, tarama kadar onemli

Su kayitlar sistematik olarak elenmelidir:

- "Sepette %25 indirim"
- "Iyi fiyat"
- sadece fiyat metni olan basliklar
- kategori kartlari
- logo veya placeholder gorseller
- stokta yok ama urunmus gibi gorunen satirlar

## Teknik Calisma Paketleri

### WP1 - Kaynak Kaydi ve Kapsama Modeli

Bu calismada:

- 81 il katalogu tutulacak
- buyuk oyuncular tek registry dosyasinda tanimlanacak
- her market icin fiyat kapsami, crawl strategy ve adres gereksinimi belirlenecek

Teslimat:

- `nationwide_platform/cities.py`
- `nationwide_platform/market_registry.py`

### WP2 - Ortak Veri Semasi

Asagidaki tablolar ortak veritabani semasinda tutulacak:

- `cities`
- `source_markets`
- `market_city_targets`
- `scrape_runs`
- `raw_products`
- `canonical_products`
- `offers`

Teslimat:

- `nationwide_platform/schema.sql`
- `nationwide_platform/storage.py`

### WP3 - Tarama Planlayicisi

Bu katman:

- her il icin ulusal market crawl target'i uretir
- adres gerekli olan marketleri isaretler
- oncelik puani verir
- gunluk/6 saatlik tazelik SLA'si atar

Teslimat:

- `nationwide_platform/planner.py`
- `nationwide_platform/bootstrap.py`

### WP4 - Urun Normalize ve Esleme Katmani

Bu katman:

- urun adini normalize eder
- marka ve gramaj tokenlarini ayirir
- alisveris listesi satirlarini market urunleriyle skorlayarak esler

Teslimat:

- `nationwide_platform/normalization.py`
- `nationwide_platform/matching.py`

### WP5 - Kaynak Adapterlari

Bu repo icinde mevcut deneme kodlari var; fakat yeni duzende adapterlar ortak protokole baglanmalidir:

- `sources/migros.py`
- `sources/carrefoursa.py`
- `sources/a101.py`
- `sources/sok.py`
- `sources/getir.py`
- `sources/macrocenter.py`
- `sources/mismar.py`
- `sources/yunus.py`
- `sources/sehzade.py`

Bu turda adapterlarin tumu yazilmadi; bunun yerine adapterlarin baglanacagi platform omurgasi kuruldu.

## Operasyon Modeli

### Tarama Katmanlari

P0:

- 81 il x 6 buyuk oyuncu hedef listesi
- adres gerektiren marketlerde "address required" task planlama

P1:

- her il icin 1 anchor adres
- buyuksehirlere 3-10 ilce anchor'i

P2:

- ilce yogunluguna gore dinamik adres havuzu
- dark store / magaza ayrimi

### Tazelik SLA

- hizli teslimat/dijital market oyunculari: 6 saatte bir
- randevulu market oyunculari: gunde 2 kez
- bolgesel/yerel oyuncular: gunde 1 kez

### Veri Kalite KPI'lari

- adres basina basarili tarama orani
- fiyat parse basari orani
- kanonik urun esleme orani
- kampanya metni yanlis pozitif orani
- gorsel doluluk orani
- ayni urunun marketler arasi eslesme orani

## Bu Turda Yapilan Muhendislik Calismasi

Bu repo icinde asagidaki temel platform kodu eklendi:

- 81 il katalogu
- buyuk oyuncular registry'si
- 81 il icin yerel market kesif gorevleri
- 81 il icin otomatik yerel market arama sorgulari
- dogrulanmis yerel market aday havuzu
- uygun adaylarin aktif source registry'ye terfi mantigi
- il-bazli yerel market kaydi
- coverage mode mantigi
- ortak SQLite semasi
- crawl target planlayicisi
- normalize / matching kutuphanesi
- bootstrap komutu
- 81 il icin yerel market kesif task tablosu
- dogrulanmis yerel market aday havuzu

Bu, tum Turkiye tarama omurgasinin ilk teknik adimidir.

## Sonraki Uygulama Adimi

1. Bu platforma ilk iki kaynak adapteri baglanacak: Migros ve CarrefourSA.
2. Her buyuk oyuncu icin adres secici / teslimat bolgesi cozumu yazilacak.
3. Mobil uygulama seed veri yerine bu platformun `offers` tablosundan beslenecek.
4. Alisveris listesi karsilastirmasi kanonik urun katalogu uzerinden gercek veriyle yapilacak.
