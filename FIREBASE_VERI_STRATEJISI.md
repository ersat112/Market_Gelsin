Firebase Veri Stratejisi
Tarih: 2026-04-01

Karar
- Firebase, bu projede ana fiyat veritabani olmayacak.
- Ana kaynak SQLite kalacak: `/Users/ersat/Desktop/Market_Gelsin/turkiye_market_platform.db`
- Mobil istemciler fiyat ve katalog verisini API uzerinden okuyacak.
- Firebase sadece hafif sinyal ve entegrasyon katmani olarak kullanilacak.

Bugunku veri buyuklugu
- DB boyutu: yaklasik `14 GB`
- `offers`: `6661831`
- `raw_products`: `6666328`
- `barcode_scan_events`: `2`
- `barcode_scan_signals`: `2`

Firebase'e gidecek veri
- `barcode_scan_events`
- `barcode_scan_signals` gunluk agregasyonu
- Ileride gerekirse cok hafif ozet dokumanlar:
- sehir bazli durum ozetleri
- barkod bazli son gorulme ozeti
- istemci cache / queue metadata

Firebase'e gitmeyecek veri
- `raw_products`
- `offers`
- `current_offers`
- gorsel katalog arsivi
- 14 GB seviyesindeki mevcut tarihsel fiyat ham verisi

Neden tum DB Firebase'e tasinmiyor
- Firestore dokuman bazli calisir; milyonlarca fiyat satirini tutmak maliyetli olur.
- Ayni verinin hem SQLite hem Firestore'da tam kopyasi operasyonel karmasa yaratir.
- Fiyat sorgulari zaten bu repo icindeki API katmaninda hazir.
- Mobil istemcinin ihtiyaci olan sey tam DB degil, filtrelenmis API cevabidir.

Onayli akış
1. Scraper ve normalization SQLite'a yazar.
2. API fiyat ve arama sorgularini SQLite uzerinden cevaplar.
3. Barkod Analiz ayri mobil app olarak scan eventlerini API'ye yollar.
4. API bu scan eventlerini SQLite'a yazar.
5. Kabul edilen scan eventleri opsiyonel olarak Firebase ve PostgreSQL'e aynalanir.

Pratik sonuc
- Firebase'e mevcut 14 GB veritabani backfill yapmayacagiz.
- Gerekirse sadece scan eventleri icin hafif backfill calistirilacak:
  `python /Users/ersat/Desktop/Market_Gelsin/scripts/backfill_firebase_scan_events.py`
