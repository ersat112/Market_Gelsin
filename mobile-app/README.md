# Market Gelsin Mobile

Bu klasor, mevcut Python scraper ve veritabani dosyalarindan ayrik duran Expo tabanli mobil MVP'dir.

## Hedef

- Kullanicinin sehrine gore online marketleri gostermek
- Urun bazli fiyat karsilastirmasi yapmak
- Alisveris listesini analiz edip:
  - urun bazli en uygun marketleri bulmak
  - tek market toplamlarini hesaplamak
  - parcali sepet toplam maliyetini gostermek
- Android APK cikisina uygun Expo/EAS altyapisi hazirlamak

## Bu iterasyonda yapilanlar

- Expo + React Native + TypeScript iskeleti kuruldu
- Sehir secimi akisi olusturuldu
- Seed veri ile market ve fiyat modeli kuruldu
- Alisveris listesi metin olarak girilip analiz ediliyor
- `eas.json` ile preview APK ve production build profilleri eklendi

## Kurulum

```bash
cd /Users/ersat/Desktop/Market_Gelsin/mobile-app
npm install
npm run start
```

Android emulator veya cihaz ile calistirmak icin:

```bash
cd /Users/ersat/Desktop/Market_Gelsin/mobile-app
npm run android
```

Preview APK build icin:

```bash
cd /Users/ersat/Desktop/Market_Gelsin/mobile-app
npx eas-cli build --platform android --profile preview
```

## Sonraki teknik adim

1. Python scraper ciktilarini normalize eden API kurulacak.
2. Mobil istemci seed veri yerine API'den fiyat cekecek.
3. Gercek cihaz konumu ile sehir secimi otomatiklestirilecek.
4. Alisveris listesi import, bildirim ve kullanici hesabi eklenecek.
