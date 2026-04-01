# ErenesAl - Market Gelsin Departman Gorevlendirme Plani

## 1. Yonetici Ozeti

Bu reposu incelenen urun, mobil uygulama degil; Python, Streamlit, SQLite, Playwright, BeautifulSoup ve requests tabanli bir market fiyat karsilastirma ve veri toplama urunudur.

Urunun bugunku durumu:

- Uygulama katmaninda birden fazla giris noktasi var: `app.py`, `app_yeni.py`, `web_demo.py`.
- Veri katmaninda birden fazla ve birbiriyle uyumsuz veritabani semasi var: `marketler.db`, `market_verisi.db`, `konya_market_verisi.db`, `Migros.db`, `Sok.db`, `Mismar.db`.
- Veri toplama motorlari birbirinden kopuk, tekrar eden ve hatalari yutan sekilde yazilmis.
- Test, CI/CD, paket yonetimi, README, deployment standardi ve guvenli sir yonetimi yok.
- Uretim kalitesine en yakin ekran `web_demo.py`; ancak bu ekran da veri kalitesi ve urunlestirme eksikleri nedeniyle final urun seviyesinde degil.

## 2. Kod Tabanindan Cikan Kritik Bulgular

### P0 - Uretim icin tek urun hatti yok

- Ayni urun icin uc farkli UI dosyasi bulunuyor.
- `app.py`, `marketler.db` veritabaniyla uyumlu degil; kod `urun_adi` ve `gorsel` alanlarini beklerken bu veritabaninda `ad` ve `resim` alanlari var.
- `web_demo.py`, `konya_market_verisi.db` ve ayri market veritabanlariyla daha tutarli calisiyor; gecici referans uygulama bunun ustunden secilmelidir.

### P0 - Veri kalitesi dengesiz

- `konya_market_verisi.db` icinde toplam 853 kayit var.
- Dagilim: Mismar 807, Sok 36, Migros 10.
- Bu dagilim market kapsama kalitesinin dengesiz oldugunu gosteriyor.
- 723 kayitta gorsel bos, `no_image.png` ya da eksik.
- Son kayitlarda Migros tarafinda kampanya metinleri urun adi olarak yakalanmis; bu, scraper filtreleme kalitesinin zayif oldugunu gosteriyor.

### P1 - Teknik borc ve operasyon riski yuksek

- Cok sayida `except:` blogu hata nedenini gizliyor.
- Birden fazla dosyada `verify=False` kullaniliyor; bu SSL dogrulamasini devre disi birakiyor.
- Scraper'lar `headless=False` ile yazildigi icin otomasyon sureci CI ortaminda zorlasiyor.
- Projede `requirements.txt`, `pyproject.toml`, `README`, `.gitignore`, Dockerfile veya CI tanimi yok.

### P1 - Urun deneyimi modern standartlara gore geride

- Kalici fiyat alarmi, kayitli filtreler, favoriler, coklu sepet karsilastirmasi, veri yenilenme tarihi, bos durumlar, hata durumu, erisilebilir etiketleme ve performans gostergeleri eksik.
- UI tutarliligi yok; uygulamanin tek marka dili, tasarim sistemi ve bilgi mimarisi bulunmuyor.

## 3. Guncel Standart Referanslari

Bu gorevlendirme, 28 Mart 2026 tarihinde resmi kaynaklarla kisa dogrulama yapilarak guncel standartlara gore hazirlanmistir:

- Streamlit dokumantasyonundaki guncel `st.cache_data` sayfasi, API referansini `v1.55.0` olarak gosteriyor ve veri sorgulari icin cache, TTL ve disk persistence seceneklerini oneriyor.
- Streamlit dokumantasyonu, `st.session_state` ile callback tabanli durum yonetimini ve proje bazli `secrets.toml` ile repo disi sir yonetimini net sekilde tarif ediyor.
- Streamlit'in resmi app testing dokumani, `AppTest` ve `pytest` ile headless testleri ve CI entegrasyonunu standart yol olarak sunuyor.
- W3C, WCAG 2.2'yi 5 Ekim 2023'te Recommendation olarak yayinladi; 21 Ekim 2025'te ISO/IEC 40500:2025 olarak da onaylandigini duyurdu.
- OWASP ASVS resmi sayfasi, ASVS 5.0.0'i guncel stabil surum olarak gosteriyor ve guvenli gelistirme ile web uygulamasi dogrulama icin temel standart olarak konumluyor.

## 4. Sirket Seviyesi Karar

Bu proje icin anlik yonetsel kararlar:

1. Referans urun hatti gecici olarak `web_demo.py` tabanli akistir.
2. Nihai hedef, tek uygulama giris noktasi, tek sema, tek scraper altyapisi ve testli release surecidir.
3. Urun once web uygulamasi olarak standardize edilecek; mobil uygulama ancak web urunu stabil olduktan sonra ayrica planlanacaktir.
4. Her departman yalniz calismayacak; tum teslimatlar capraz departman review ile kapanacaktir.

## 5. Departman Gorevlendirmeleri

## Yazilim Gelistirme (Ar-Ge)

Misyon:
Tek urun kod tabani olusturmak, veri toplama motorlarini standardize etmek ve uygulamayi bakimi kolay bir yapiya tasimak.

Sorumluluklar:

- `app.py`, `app_yeni.py`, `web_demo.py` icinden tek resmi uygulama giris noktasini secmek ve digerlerini arsivlemek.
- Tek veritabani semasi tanimlamak: `products`, `markets`, `price_snapshots`, `scrape_runs`, `alerts`.
- Scraper katmanini adapter mimarisine cevirmek:
  - `sources/migros.py`
  - `sources/sok.py`
  - `sources/mismar.py`
- Kampanya metni, placeholder gorsel, stokta yok, eksik fiyat, bozuk kategori gibi kayitlari filtreleyen veri temizleme kurallari yazmak.
- Lokal gelistirme standardini kurmak:
  - `pyproject.toml`
  - bagimlilik kilitleme
  - lint
  - format
  - type check
- Ekrani komponentlere ayirmak:
  - arama
  - filtre paneli
  - urun karti
  - sepet karsilastirma
  - fiyat gecmisi
  - veri tazelik gostergesi
- Fiyat alarmi ozelligini gercek veri modeline baglamak; buton animasyonu degil, kalici kural mekanizmasi olarak yazmak.

Teslimatlar:

- Tek calisan uygulama dosyasi
- Tek migration akisi
- Tek scraper framework
- Temel test kapsami
- Teknik borc temizleme listesi kapatilmis sprint board

Basari kriteri:

- Uygulama tek komutla calisiyor.
- Tüm marketler ortak semaya veri yaziyor.
- UI tarafinda runtime schema hatasi kalmiyor.
- En az bir gunluk veri yenileme isi hatasiz tamamlanabiliyor.

## Proje ve Urun Yonetimi

Misyon:
Bu dağinik prototipi urun yol haritasina, sprint planina ve release kriterlerine baglamak.

Sorumluluklar:

- V1 kapsamini kilitlemek:
  - urun arama
  - market filtreleme
  - kategori filtreleme
  - sepet karsilastirma
  - fiyat alarmi
  - son guncellenme bilgisi
- V1.1 kapsamini ayirmak:
  - fiyat gecmisi grafikleri
  - kullanici hesabı
  - favoriler
  - bolgesel market secimi
- Tüm ekipler icin Definition of Done yayinlamak.
- Haftalik risk panosu kurmak:
  - veri kapsama
  - scraper kirilma orani
  - sayfa acilis hizi
  - kritik bug sayisi
- Uygulamanin artik "Konya odakli demo" mu yoksa "genel market karsilastirma urunu" mu oldugunu netlestirmek.
- MVP icin North Star KPI belirlemek:
  - aranip bulunan urun orani
  - marketler arasi esitlenebilen urun orani
  - aktif kullanici basina sepete eklenen urun sayisi

Teslimatlar:

- 6 haftalik teslim takvimi
- Sprint backlog
- Kabul kriterleri
- Release checklist

Basari kriteri:

- Her ekip neyi neden yaptigini bilir.
- Kapsam kaymasi azalir.
- Her sprint sonunda demo alinabilir.

## Kalite Guvencesi ve Test (QA)

Misyon:
Uygulamanin veri, islev, performans ve regresyon kalitesini olculur hale getirmek.

Sorumluluklar:

- Test piramidi kurmak:
  - unit test
  - scraper parser testleri
  - Streamlit `AppTest` tabanli UI testleri
  - kritik akislarda end-to-end smoke testi
- Veri kalitesi testleri yazmak:
  - fiyat > 0
  - urun adi minimum kalite kurali
  - kampanya metni urun adi olamaz
  - market kapsama esigi
  - gorsel doluluk orani
- Release oncesi manuel checklist olusturmak:
  - mobil gorunum
  - bos durumlar
  - hata mesajlari
  - sepet akisi
  - filtre kombinasyonlari
- Performans benchmark seti cikarmak:
  - ilk ekran yuklenme suresi
  - 500+ kayitta liste tepkisi
  - resim yukleme davranisi
- Scraper regression suite kurmak; DOM degisikliklerinde uyari uretecek parser snapshot yapisi olusturmak.

Teslimatlar:

- `tests/` klasoru
- Veri kalite raporu
- Release onayi icin QA raporu

Basari kriteri:

- Kritik akislarda otomatik regresyon kapsami olur.
- Veri kirlenmesi release sonrasi degil, CI sirasinda yakalanir.

## Tasarim (UI/UX)

Misyon:
Uygulamayi demo hissinden cikarip guven veren, hizli, anlasilir bir fiyat karsilastirma deneyimine cevirmek.

Sorumluluklar:

- Bilgi mimarisi kurmak:
  - ana liste
  - urun detay/karsilastirma
  - sepet
  - alarmlar
  - veri tazelik durumu
- Tasarim sistemi tanimlamak:
  - renk tokenlari
  - tipografi
  - bos durumlar
  - hata durumlari
  - kart yapisi
  - rozetler
- WCAG 2.2 uyumlu kontrast, odak durumu, klavye gezinme ve anlasilir metin kurallarini tanimlamak.
- Market bazli fiyat farki, avantaj yuzdesi ve son guncellenme bilgisini kullaniciya sezgisel gostermek.
- "Sepete ekle" davranisini sadece liste hafizasi olmaktan cikarip gercek karsilastirma deneyimine donusturmek.
- Mobil dar ekran, tablet ve masaustu icin responsive davranisi figma ve acceptance kriterleriyle netlestirmek.

Teslimatlar:

- Yuksek sadakatli ekranlar
- Tasarim token dosyasi
- Erişilebilirlik checklist'i

Basari kriteri:

- Yeni kullanici ilk 30 saniyede urun arayip en ucuz marketi anlayabilir.
- Kullanici kampanya, stok ve veri tazelik bilgisini karistirmadan okuyabilir.

## DevOps ve Altyapi

Misyon:
Projeyi kisiden bagimsiz, tekrar edilebilir ve guvenli bir release hattina baglamak.

Sorumluluklar:

- Proje standardini kurmak:
  - `Makefile` veya gorev scriptleri
  - sanal ortam standardi
  - bagimlilik kurulum akisi
- CI kurmak:
  - lint
  - test
  - package build
  - artifact
- Gecelik veri yenileme pipeline'i kurmak.
- Scrape run loglari, hata orani, veri sayisi ve kapsama metriği icin gozlemlenebilirlik eklemek.
- `headless=True` uyumlu scraper calistirma modu ve gerekli fallback stratejisi tanimlamak.
- Sir yonetimini repo disina tasimak:
  - `.streamlit/secrets.toml`
  - ortam degiskenleri
- Yedekleme ve veri geri donus plani cikarmak.

Teslimatlar:

- CI/CD pipeline
- deployment ortami
- scheduler
- loglama ve alarm mekanizmasi

Basari kriteri:

- Yeni ortam 30 dakika icinde ayağa kalkar.
- Her release oncesi otomatik kalite kapi calisir.
- Veri yenileme isi basarisiz olursa ekip uyari alir.

## Satis ve Pazarlama

Misyon:
Urunun kime, hangi problem icin ve nasil konumlanacagini netlestirmek.

Sorumluluklar:

- Hedef kullanici segmentlerini ayirmak:
  - fiyat hassasiyeti yuksek aileler
  - ogrenciler
  - toplu alisveris yapan haneler
  - lokal market takipcileri
- Konumlama metnini yazmak:
  - "en ucuzu bul"
  - "market market gezmeden karar ver"
  - "guncel fiyat takibi"
- Landing page mesaji, store metinleri ve demo videolari icin icerik planlamak.
- Rakip analizi yapmak:
  - market uygulamalari
  - fiyat karsilastirma siteleri
  - sepet optimizasyonu sunan servisler
- Beta kullanici toplama ve geri bildirim akisini olusturmak.

Teslimatlar:

- positioning dokumani
- lansman sayfasi icerigi
- beta kullanici listesi
- geri bildirim formu

Basari kriteri:

- Urunun degeri 10 saniyede anlatilir.
- Ilk beta grubu gercek ihtiyaca gore secilir.

## Musteri Basarisi ve Teknik Destek

Misyon:
Kullanici geri bildirimini urun iyilestirme motoruna cevirmek.

Sorumluluklar:

- Sorun siniflandirma sistemi kurmak:
  - veri hatasi
  - eksik market
  - bozuk fiyat
  - gorsel sorunu
  - performans
  - kullanilabilirlik
- Ticket akisini tanimlamak:
  - aciliyet
  - sahiplik
  - SLA
  - kapanis kriteri
- SSS ve destek metinleri yazmak.
- Kullanici tarafindan raporlanan hatalari veri ekibine ve Ar-Ge'ye otomatik aktaran akisi kurmak.
- Fiyat alarmi, veri guncellik zamani ve market kapsami gibi kritik alanlar icin bilgilendirici yardim metinleri hazirlamak.

Teslimatlar:

- destek paneli yapisi
- sik sorulan sorular
- ticket etiketleme sozlugu

Basari kriteri:

- Kullanici raporu kaybolmaz.
- Aynı problem ikinci kez "ne oldugu anlasilmadan" kapanmaz.

## Is Analizi (Business Analysis)

Misyon:
Veri modeli ile kullanici ihtiyaci arasindaki kopuklugu kapatmak.

Sorumluluklar:

- Temel kullanici senaryolarini netlestirmek:
  - tek urun en ucuz market bulma
  - alisveris listesi toplam sepet optimizasyonu
  - belirli marketi takip etme
  - fiyat dusunce bildirim alma
- Kanonik is kurallarini yazmak:
  - ayni urun nasil eslesir
  - kategori standardi nasil olur
  - kampanya metni urun mudur degil midir
  - gorsel eksikligi kabul kriteri nedir
  - veri tazeligi esigi kac saattir
- KPI ve raporlama modelini cikarmak.
- Veri kapsama ve dogruluk olcumleri icin is tanimlarini yazmak.

Teslimatlar:

- PRD
- is kurallari dokumani
- veri sozlugu
- KPI seti

Basari kriteri:

- Ekibin "ayni urun" tanimi ortaktir.
- Veri ekipleri ile urun ekibi ayni dili kullanir.

## 6. Capraz Ekip Calisma Modeli

Her sprintte su zincir zorunludur:

1. Is Analizi + Urun Yonetimi is kuralini netlestirir.
2. UI/UX akisi ve acceptance kriterini baglar.
3. Ar-Ge teknik cozum ve veri modelini uygular.
4. QA veri ve UI regresyonunu calistirir.
5. DevOps pipeline, deploy ve izleme kapilarini acmadan release cikmaz.
6. Musteri Basarisi beta geri bildirimini toplar.
7. Satis/Pazarlama sadece dogrulanmis urun degerlerini disariya tasir.

## 7. 6 Haftalik Icra Plani

### Hafta 1

- Referans uygulama secimi
- repo temizligi
- teknik audit backlog
- ortak sema tasarimi
- PRD ciktisi

### Hafta 2

- tek veritabani katmani
- scraper adapter tasarimi
- tasarim sistemi temel kararlar
- test altyapisi kurulumu

### Hafta 3

- UI'nin yeni bilgi mimarisine tasinmasi
- veri kalite filtreleri
- ilk otomatik test paketi
- CI kurulumu

### Hafta 4

- fiyat alarmi
- sepet karsilastirma iyilestirmesi
- veri tazeligi ve hata durumlari
- erisilebilirlik duzeltmeleri

### Hafta 5

- beta release
- telemetry ve ticket akisi
- landing page ve iletisim materyalleri

### Hafta 6

- bug bash
- performans iyilestirmesi
- release aday surum
- canliya cikis onayi

## 8. Zorunlu Kabul Kriterleri

Bu urun "tamamlandi" sayilmayacak, ta ki su maddeler kapanana kadar:

- Tek uygulama giris noktasi olacak.
- Tek veri semasi olacak.
- Scraper basarisizligi loglanacak ve uyari uretecek.
- Kritik akislarda otomatik test olacak.
- UI WCAG 2.2 temel kriterlerini saglayacak.
- Sirlar repoda tutulmayacak.
- Veri guncellenme zamani ekranda gorunecek.
- Kampanya metni ve bozuk urun isimleri filtrelenecek.
- Dokumantasyon ve kurulum talimati olacak.

## 9. Bugunden Itibaren Gecen Emir

Her departman bu projeyi "demo" degil "urun" gibi ele alacaktir.

- Ar-Ge tek kod tabanina inmeyen hicbir gelistirmeyi kabul etmeyecek.
- Urun Yonetimi kapsami yazili hale getirmeden is acmayacak.
- QA testsiz kritik ozellik kapatmayacak.
- UI/UX erisilebilirliksiz ekran onaylamayacak.
- DevOps CI kapisi olmadan release vermeyecek.
- Satis/Pazarlama dogrulanmamis vaatte bulunmayacak.
- Musteri Basarisi geri bildirimleri yapilandirmadan iletmeyecek.
- Is Analizi ortak veri kurali cikarmadan backlog kapatmayacak.

Bu proje ekip calismasiyla, ortak kalite standardiyla ve tek urun vizyonuyla ilerleyecektir.
