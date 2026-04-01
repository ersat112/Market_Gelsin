import { CityId, Market, PriceEntry } from "../types";

export const cities: Array<{ id: CityId; name: string; subtitle: string }> = [
  {
    id: "konya",
    name: "Konya",
    subtitle: "Bu repodaki mevcut scraper verisinin referans sehri"
  },
  {
    id: "ankara",
    name: "Ankara",
    subtitle: "Mobil akisin sehir bazli mimarisini gosteren seed veri"
  },
  {
    id: "istanbul",
    name: "Istanbul",
    subtitle: "Cok marketli sehir kurgusu icin seed veri"
  }
];

export const markets: Market[] = [
  { id: "mismar-konya", name: "Mismar", cityId: "konya", badge: "Yerel", eta: "35 dk" },
  { id: "migros-konya", name: "Migros Sanal Market", cityId: "konya", badge: "Ulusal", eta: "45 dk" },
  { id: "sok-konya", name: "Sok Market", cityId: "konya", badge: "Ulusal", eta: "40 dk" },
  { id: "migros-ankara", name: "Migros Sanal Market", cityId: "ankara", badge: "Ulusal", eta: "35 dk" },
  { id: "carrefour-ankara", name: "CarrefourSA", cityId: "ankara", badge: "Ulusal", eta: "50 dk" },
  { id: "a101-ankara", name: "A101 Kapi da", cityId: "ankara", badge: "Indirim", eta: "60 dk" },
  { id: "migros-istanbul", name: "Migros Sanal Market", cityId: "istanbul", badge: "Ulusal", eta: "30 dk" },
  { id: "carrefour-istanbul", name: "CarrefourSA", cityId: "istanbul", badge: "Ulusal", eta: "35 dk" },
  { id: "getir-buyuk-istanbul", name: "Getir Buyuk", cityId: "istanbul", badge: "Hizli", eta: "20 dk" }
];

export const priceEntries: PriceEntry[] = [
  {
    id: "konya-sok-sut",
    cityId: "konya",
    marketId: "sok-konya",
    productName: "Mis UHT Sut %3.1 Yagli 1 L",
    category: "Sut ve Kahvaltilik",
    price: 37.5,
    unit: "1 L",
    freshnessLabel: "2 saat once"
  },
  {
    id: "konya-migros-sut",
    cityId: "konya",
    marketId: "migros-konya",
    productName: "Migros Sut 1 L",
    category: "Sut ve Kahvaltilik",
    price: 39.95,
    unit: "1 L",
    freshnessLabel: "35 dk once"
  },
  {
    id: "konya-mismar-sut",
    cityId: "konya",
    marketId: "mismar-konya",
    productName: "Gunluk Sut 1 L",
    category: "Sut ve Kahvaltilik",
    price: 42.5,
    unit: "1 L",
    freshnessLabel: "Bugun"
  },
  {
    id: "konya-sok-makarna",
    cityId: "konya",
    marketId: "sok-konya",
    productName: "Piyale Spagetti 500 G",
    category: "Temel Gida",
    price: 15.5,
    unit: "500 G",
    freshnessLabel: "2 saat once"
  },
  {
    id: "konya-migros-makarna",
    cityId: "konya",
    marketId: "migros-konya",
    productName: "Migros Spagetti Makarna 500 G",
    category: "Temel Gida",
    price: 17.9,
    unit: "500 G",
    freshnessLabel: "35 dk once"
  },
  {
    id: "konya-mismar-makarna",
    cityId: "konya",
    marketId: "mismar-konya",
    productName: "Burgu Makarna 500 G",
    category: "Temel Gida",
    price: 18.9,
    unit: "500 G",
    freshnessLabel: "Bugun"
  },
  {
    id: "konya-sok-patates",
    cityId: "konya",
    marketId: "sok-konya",
    productName: "Patates Kg",
    category: "Meyve Sebze",
    price: 17.9,
    unit: "1 Kg",
    freshnessLabel: "2 saat once"
  },
  {
    id: "konya-migros-patates",
    cityId: "konya",
    marketId: "migros-konya",
    productName: "Patates 1 Kg",
    category: "Meyve Sebze",
    price: 24.9,
    unit: "1 Kg",
    freshnessLabel: "35 dk once"
  },
  {
    id: "konya-mismar-patates",
    cityId: "konya",
    marketId: "mismar-konya",
    productName: "Patates Taze 1 Kg",
    category: "Meyve Sebze",
    price: 21.5,
    unit: "1 Kg",
    freshnessLabel: "Bugun"
  },
  {
    id: "konya-sok-yag",
    cityId: "konya",
    marketId: "sok-konya",
    productName: "Yudum Aycicek Yagi 1 L",
    category: "Temel Gida",
    price: 84.9,
    unit: "1 L",
    freshnessLabel: "2 saat once"
  },
  {
    id: "konya-migros-yag",
    cityId: "konya",
    marketId: "migros-konya",
    productName: "Migros Aycicek Yagi 1 L",
    category: "Temel Gida",
    price: 79.95,
    unit: "1 L",
    freshnessLabel: "35 dk once"
  },
  {
    id: "konya-mismar-yag",
    cityId: "konya",
    marketId: "mismar-konya",
    productName: "Aycicek Yagi 1 L",
    category: "Temel Gida",
    price: 82.9,
    unit: "1 L",
    freshnessLabel: "Bugun"
  },
  {
    id: "konya-sok-ekmek",
    cityId: "konya",
    marketId: "sok-konya",
    productName: "Normal Ekmek",
    category: "Firindan",
    price: 15,
    unit: "1 Adet",
    freshnessLabel: "2 saat once"
  },
  {
    id: "konya-mismar-ekmek",
    cityId: "konya",
    marketId: "mismar-konya",
    productName: "Normal Ekmek",
    category: "Firindan",
    price: 13,
    unit: "1 Adet",
    freshnessLabel: "Bugun"
  },
  {
    id: "konya-migros-yumurta",
    cityId: "konya",
    marketId: "migros-konya",
    productName: "Gezen Tavuk Yumurtasi 10 Lu",
    category: "Sut ve Kahvaltilik",
    price: 76.95,
    unit: "10 Lu",
    freshnessLabel: "35 dk once"
  },
  {
    id: "konya-sok-yumurta",
    cityId: "konya",
    marketId: "sok-konya",
    productName: "Yumurta 10 Lu",
    category: "Sut ve Kahvaltilik",
    price: 72.5,
    unit: "10 Lu",
    freshnessLabel: "2 saat once"
  },
  {
    id: "ankara-migros-sut",
    cityId: "ankara",
    marketId: "migros-ankara",
    productName: "Migros Sut 1 L",
    category: "Sut ve Kahvaltilik",
    price: 38.95,
    unit: "1 L",
    freshnessLabel: "20 dk once"
  },
  {
    id: "ankara-carrefour-sut",
    cityId: "ankara",
    marketId: "carrefour-ankara",
    productName: "Carrefour Sut 1 L",
    category: "Sut ve Kahvaltilik",
    price: 40.25,
    unit: "1 L",
    freshnessLabel: "1 saat once"
  },
  {
    id: "ankara-a101-sut",
    cityId: "ankara",
    marketId: "a101-ankara",
    productName: "Birsen Sut 1 L",
    category: "Sut ve Kahvaltilik",
    price: 36.9,
    unit: "1 L",
    freshnessLabel: "10 dk once"
  },
  {
    id: "ankara-migros-patates",
    cityId: "ankara",
    marketId: "migros-ankara",
    productName: "Patates 1 Kg",
    category: "Meyve Sebze",
    price: 22.9,
    unit: "1 Kg",
    freshnessLabel: "20 dk once"
  },
  {
    id: "ankara-carrefour-patates",
    cityId: "ankara",
    marketId: "carrefour-ankara",
    productName: "Patates 1 Kg",
    category: "Meyve Sebze",
    price: 19.95,
    unit: "1 Kg",
    freshnessLabel: "1 saat once"
  },
  {
    id: "ankara-a101-patates",
    cityId: "ankara",
    marketId: "a101-ankara",
    productName: "Patates 1 Kg",
    category: "Meyve Sebze",
    price: 18.75,
    unit: "1 Kg",
    freshnessLabel: "10 dk once"
  },
  {
    id: "ankara-migros-yag",
    cityId: "ankara",
    marketId: "migros-ankara",
    productName: "Aycicek Yagi 1 L",
    category: "Temel Gida",
    price: 79.5,
    unit: "1 L",
    freshnessLabel: "20 dk once"
  },
  {
    id: "ankara-carrefour-yag",
    cityId: "ankara",
    marketId: "carrefour-ankara",
    productName: "Aycicek Yagi 1 L",
    category: "Temel Gida",
    price: 83.9,
    unit: "1 L",
    freshnessLabel: "1 saat once"
  },
  {
    id: "ankara-a101-yag",
    cityId: "ankara",
    marketId: "a101-ankara",
    productName: "Aycicek Yagi 1 L",
    category: "Temel Gida",
    price: 77.9,
    unit: "1 L",
    freshnessLabel: "10 dk once"
  },
  {
    id: "istanbul-migros-sut",
    cityId: "istanbul",
    marketId: "migros-istanbul",
    productName: "Migros Sut 1 L",
    category: "Sut ve Kahvaltilik",
    price: 40.5,
    unit: "1 L",
    freshnessLabel: "25 dk once"
  },
  {
    id: "istanbul-carrefour-sut",
    cityId: "istanbul",
    marketId: "carrefour-istanbul",
    productName: "Carrefour Sut 1 L",
    category: "Sut ve Kahvaltilik",
    price: 39.9,
    unit: "1 L",
    freshnessLabel: "40 dk once"
  },
  {
    id: "istanbul-getir-sut",
    cityId: "istanbul",
    marketId: "getir-buyuk-istanbul",
    productName: "Getir Sut 1 L",
    category: "Sut ve Kahvaltilik",
    price: 41.9,
    unit: "1 L",
    freshnessLabel: "15 dk once"
  },
  {
    id: "istanbul-migros-makarna",
    cityId: "istanbul",
    marketId: "migros-istanbul",
    productName: "Spagetti Makarna 500 G",
    category: "Temel Gida",
    price: 18.5,
    unit: "500 G",
    freshnessLabel: "25 dk once"
  },
  {
    id: "istanbul-carrefour-makarna",
    cityId: "istanbul",
    marketId: "carrefour-istanbul",
    productName: "Burgu Makarna 500 G",
    category: "Temel Gida",
    price: 17.95,
    unit: "500 G",
    freshnessLabel: "40 dk once"
  },
  {
    id: "istanbul-getir-makarna",
    cityId: "istanbul",
    marketId: "getir-buyuk-istanbul",
    productName: "Makarna 500 G",
    category: "Temel Gida",
    price: 19.9,
    unit: "500 G",
    freshnessLabel: "15 dk once"
  }
];
