# Kozmetik Kanali Durumu

Tarih: 2026-03-31

## Canli Kaynaklar

- `eveshop_online`
  - adapter: `shopify_json_catalog`
  - durum: `live`
  - kapsama: `81 il`
  - not: `products.json` uzerinden katalog cekiliyor
- `tshop_online`
  - adapter: `nextjs_sitemap_or_api`
  - durum: `live`
  - kapsama: `81 il`
  - not: `products.xml` + urun sayfasi JSON-LD akisi uzerinden kontrollu katalog cekiliyor
- `flormar_online`
  - adapter: `headless_web_catalog`
  - durum: `live`
  - kapsama: `81 il`
  - not: `sitemap-products-1.xml.gz` + urun sayfasi meta/schema akisi uzerinden kontrollu katalog cekiliyor
- `gratis_online`
  - adapter: `product_sitemap_plus_page_parse`
  - durum: `live`
  - kapsama: `81 il`
  - not: `Product-tr-TRY.xml` + sayfaya gomulu `productData` nesnesi uzerinden kontrollu katalog cekiliyor
- `rossmann_online`
  - adapter: `react_graphql_catalog`
  - durum: `live`
  - kapsama: `81 il`
  - not: resmi `elastic.php` katalog endpointi uzerinden tam katalog cekiliyor
- `kozmela_online`
  - adapter: `custom_html_or_api_catalog`
  - durum: `live`
  - kapsama: `81 il`
  - not: koleksiyon sayfalarindaki gomulu `PRODUCT_DATA` nesneleri uzerinden kontrollu katalog cekiliyor

## Planli Kaynaklar

- `watsons_online`
  - adapter ailesi: `akamai_guarded_web_or_app`
  - not: 2026-03-31 tarihinde ana sayfa, robots, sitemap ve urun sayfalari 403 donuyor
- `sephora_online`
  - adapter ailesi: `akamai_guarded_web_or_app`
  - not: 2026-03-31 tarihinde ana sayfa ve sitemap yuzeyleri 403 donuyor
- `yves_rocher_online`
  - adapter ailesi: `akamai_guarded_web_or_app`
  - not: 2026-03-31 tarihinde kategori ve sitemap yuzeyleri 403 donuyor
## Barkod Notu

- `EveShop` su an guvenilir GTIN vermiyor.
- `T-Shop`, `Flormar`, `Gratis`, `Rossmann` ve `Kozmela` tarafinda guvenilir barkod akisi var.
- Bu nedenle barkod kolonuna sahte veri yazilmiyor.
- Barkod Analiz entegrasyonunda `T-Shop`, `Flormar`, `Gratis`, `Rossmann` ve `Kozmela` barkod bazli; `EveShop` ise isim/marka/kategori/fiyat bazli akisi besler.

## Sonraki En Verimli Siralama

1. `watsons_online`
2. `sephora_online`
3. `yves_rocher_online`
4. `image_url` backfill kalite kontrolu
5. Barkod Analiz tarafinda kozmetik sorgularinin sertlestirilmesi
