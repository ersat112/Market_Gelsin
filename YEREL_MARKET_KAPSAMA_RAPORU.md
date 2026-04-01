# Yerel Market Kapsama Raporu

## Mevcut Durum

- 81 il icin yerel market kesif gorevi uretildi.
- 81 il icin 4'er adet arama sorgusu backlog'a yaziliyor.
- Dogrulanmis yerel market havuzu buyuk sehirlerle sinirli kalmayip bolgesel oyuncularla genisletildi.
- Uygun bulunan dogrulanmis adaylar aktif source registry'ye terfi ettirildi.
- 81 ilin tamami `city_local_coverage_status` tablosunda kapsama durumuyla tutuluyor.
- Guncel durum: 55 ilde dogrulanmis yerel kaynak, 26 ilde aktif kesif backlog'u.
- Aktif registry buyuklugu: 72 `source_markets`, 631 `market_city_targets`, 64 `local_market_candidates`.

## Aktif Yerel Kaynaklar

- Adana: Groseri
- Adiyaman: Kahta Online Market
- Afyonkarahisar: Soz Sanal Market
- Aksaray: Depoo Sanal Market
- Amasya: Amasya Et Urunleri Market
- Ankara: Yunus Market Online
- Antalya: Saladdo
- Aydin: Bilmar Market
- Balikesir: Balikesir Sanal Market
- Bartin: Marketim Bartin
- Batman: Batman Sanal Market
- Bingol: Bingol Market
- Bolu: Biistek Sanal Market
- Bursa: Ozhan Market
- Canakkale: delVita
- Corum: Gelirr Sanal Market
- Denizli: Alp Supermarket
- Duzce: Duzpas
- Diyarbakir: Carmar Sanal Market
- Elazig: Isik Market
- Edirne: Margi Market
- Eskisehir: Eskisehir Market
- Erzincan: AVEME, Ayaydin Gross Market
- Erzurum: Guvendik Hipermarketcilik
- Gaziantep: Nokta Jet, Gaziantep Gross Market
- Giresun: Ankamar, Afta Market
- Hatay: Hat1
- Isparta: IYAS
- Istanbul: Yalla Market, Showmar Hipermarketleri
- Izmir: IZMAR, Kuzey Market, Basdas Online Market, Baris Gross Market
- Kahramanmaras: Maras Market
- Karaman: Sele
- Kayseri: Sehzade Online
- Kocaeli: Taso Market
- Konya: Mismar Online
- Kirklareli: Onur Market
- Kutahya: SUMA / Sultan Market
- Malatya: Ozkaraca AVM
- Manisa: K-Depo
- Mersin: Groseri
- Nevsehir: Geliver
- Osmaniye: Yalcin Marketler Zinciri
- Ordu: Kalafatlar Market, Gelsineve, Ankamar
- Rize: Kale Market
- Sakarya: Atilim Sanal Market
- Samsun: Samsun Market
- Sanliurfa: Evdesiparis
- Sivas: Besler Market
- Tokat: Erenler Supermarket
- Trabzon: Asya Market
- Tekirdag: Onur Market
- Van: Roka Market
- Yalova: Centa AVM
- Yozgat: Simdi Kapida / Gimat
- Zonguldak: Akbal Market

## Model Mantigi

- `source_markets`: planlayiciya dahil edilen aktif kaynaklar
- `local_market_candidates`: sehir bazli dogrulanmis veya arastirma asamasindaki yerel oyuncular
- `city_local_discovery_tasks`: 81 ilin her biri icin kesif gorevi
- `city_local_discovery_queries`: her il icin otomatik uretilen arama sorgulari
- `city_local_coverage_status`: ilin yerel kaynak bakimindan guncel durumu

## Sonraki Adim

- Kalan 26 il icin tarama notlari [KALAN_ILLER_TARAMA_RAPORU.md](./KALAN_ILLER_TARAMA_RAPORU.md) dosyasinda sehir bazli nedenleriyle tutuluyor.
- Dogrulanan yeni oyuncular `local_market_candidates` havuzundan aktif source registry'ye otomatik terfi ettirildi.
- Dogrulanan yeni sehirler icin oncelik sirasiyla `Bilmar` ve `Marketim Bartin / Marul.com` veri akislari degerlendirilecek.
- `Amasya Et Urunleri Market` artik canli adaptere sahip ve ilk ingest dogrulamasi tamamlandi.
- `Atilim Sanal Market` artik canli adaptere sahip ve ilk ingest dogrulamasi tamamlandi.
- `Evdesiparis` artik canli adaptere sahip ve ilk ingest dogrulamasi tamamlandi.
- `IZMAR` artik canli adaptere sahip ve ilk ingest dogrulamasi tamamlandi.
- `Tarim Kredi Koop Market` artik ulusal kontrollu canli adaptere sahip ve ilk ingest dogrulamasi tamamlandi.
- `Bizim Toptan Online Market` artik ulusal kontrollu canli adaptere sahip ve ilk ingest dogrulamasi tamamlandi.
- `Bingol Market` icin Shopify adapter kodu hazir; canli ingest su an Cloudflare korumasi nedeniyle teyit bekliyor.
- Ulusal fallback hattinda `Cepte Sok` calisiyor; yerel kesif bekleyen iller icin Faz 1 kontrollu akis omurgasi aktif.
- Adres secimi isteyen yerel oyuncular icin session / teslimat bolgesi adapterleri yazilacak.
