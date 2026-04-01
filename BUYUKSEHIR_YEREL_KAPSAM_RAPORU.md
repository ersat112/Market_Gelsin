Buyuksehir Yerel Kapsam Raporu
Tarih: 2026-04-01

Ozet
- `30` buyuksehir ilinin yerel market kapsami ayri takip ediliyor.
- En guclu canli kapsama:
  - `Izmir` -> `4/4` yerel market canli
  - `Ordu` -> `3/3` yerel market canli
  - `Ankara` -> `1/1`
  - `Istanbul` -> `1/2`
  - `Konya` -> `1/2`
- Tek marketli ve canli olan buyuksehirler:
  - `Adana`
  - `Antalya`
  - `Balikesir`
  - `Diyarbakir`
  - `Erzurum`
  - `Eskisehir`
  - `Kayseri`
  - `Kahramanmaras`
  - `Kocaeli`
  - `Manisa`
  - `Mersin`
  - `Sakarya`
  - `Sanliurfa`
  - `Tekirdag`
  - `Trabzon`

Eksik veya canli olmayan buyuksehir yerel marketleri
- `Gaziantep` -> `0/2`
  - `gaziantep_gross`
  - `nokta_jet_gaziantep`
- `Aydin` -> `0/1`
  - `bilmar_market_aydin`
- `Bursa` -> `0/1`
  - `ozhan_bursa`
- `Denizli` -> `0/1`
  - `alp_supermarket_denizli`
- `Hatay` -> `0/1`
  - `hat1_hatay`
- `Malatya` -> `0/1`
  - `ozkaraca_malatya`
- `Samsun` -> `0/1`
  - `samsun_market`
- `Van` -> `0/1`
  - `roka_van`
- `Mardin` -> `0/0`
- `Mugla` -> `0/0`

Canli ama genisletme gereken sehirler
- `Ankara`
  - `yunus_market_ankara` canli
  - son basarili run: `3934`
  - `358/358` urun yazildi
  - ornekler: `TORKU ISIL ISLEM KANGAL SUCUK KG 990 TL`, `DANA KONTRFILE KG 925 TL`
- `Istanbul`
  - `showmar_istanbul` canli
  - son hizlandirilmis run: `3939`
  - `2642/2642` urun yazildi
  - ikinci yerel kaynak eksik
- `Konya`
  - `mismar_konya` canli
  - `celikkayalar_konya` dogrulanmis; public web yuzeyi `OneLink` mobil koprusu verdigi icin `mobile_app_session` collector bekliyor

Bugun tam kataloga yaklasan canli marketler
- `basdas_online_izmir`
  - son run: `3936`
  - `1468/1468`
- `izmar_izmir`
  - son run: `3937`
  - `1059/1059`
- `kuzey_market_izmir`
  - son run: `3938`
  - `1912/1912`
- `showmar_istanbul`
  - son run: `3939`
  - `2642/2642`
- `balikesir_sanal_market`
  - son run: `3946`
  - `77/77`
- `maras_market_kahramanmaras`
  - son run: `3942`
  - `73/73`

Bugun netlesen problemli collector durumu
- `carmar_diyarbakir`
  - son basarili run: `259`
- `taso_market_kocaeli`
  - son basarili run: `39`
  - hizlandirilmis tam katalog denemesi agir kuyruga alindi
- `onur_market_tekirdag`
  - son basarili run: `40`
  - hizlandirilmis tam katalog denemesi agir kuyruga alindi
- `asya_market_trabzon`
  - son basarili run: `39`
  - hizlandirilmis tam katalog denemesi sonraki tekil kuyruğa alindi
- `k_depo_manisa`
  - son basarili run: `30`
  - hizlandirilmis tam katalog denemesi agir kuyruga alindi
- `yunus_market_ankara`
  - tam katalog replay denemesi Playwright tarafinda agirlasti; ayri uzun kuyruga alindi
- `mismar_konya`
  - sitemap bazli tam katalog replay denemesi binlerce urun linki nedeniyle ayri uzun kuyruga alindi
- `saladdo_antalya`
  - Wix tabanli tam katalog replay denemesi ayri uzun kuyruga alindi
- `guvendik_erzurum`
  - WooCommerce tam katalog replay denemesi ayri uzun kuyruga alindi

Sonraki teknik siralama
1. `Ozhan / Bursa`
2. `Gaziantep Gross` ve `Nokta Jet`
3. `Alp / Denizli`
4. `Celikkayalar / Konya`, `Hat1 / Hatay` app-session hatti
5. `Ozkaraca / Malatya`, `Roka / Van`

Hizlandirma notlari
- `HtmlStorefrontAdapter`, `TicimaxSitemapAdapter` ve `IdeaSoftSitemapAdapter` ailelerine `curl` fallback eklendi.
- Bu degisiklik ozellikle `Kocaeli / Taso`, `Tekirdag / Onur`, `Trabzon / Asya` gibi `requests` tabanli DNS-SSL takilmalarini azaltmak icin yapildi.
- Tam katalog hizlandirma turunda su ailelerin limitleri buyutuldu: `WooCommerceHtml`, `TSoftCategory`, `TSoftLegacyGrid`, `Gelsineve`, `OpenCartSearch`, `EskisehirMarketCategory`, `PrestaShopElementor`, `WixStores`, `SitemapProductDetail`, `KommerzAjax`, `Basdas`, `Izmar`, `NextJsCard`, `Ticimax`, `IdeaSoft`, `YepPos`, `PlaywrightHtml`, `WordPressRest`.
- Collector SQLite baglantisi `WAL` moduna alindi.
- PostgreSQL migration scriptleri artik SQLite'a `read-only` baglaniyor; boylece sonraki full-history migration kosulari collector ile daha az carpışacak.
- `storefront_probe` artik `App Store / Google Play / OneLink` sinyallerini `app_only` olarak ayiriyor.
- Bu sayede `celikkayalar_konya` ve `hat1_hatay` gereksiz web probe kuyrugundan cikti; dogrudan `mobile_app_session` hattina alindi.
- Son manuel probe:
  - `ozhan_bursa` -> `catalog_visible_no_cards`
  - `ozkaraca_malatya` -> `corp_site_only` ama `woocommerce_candidate`
