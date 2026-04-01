81 Il Toplu Cekim Komutu
Tarih: 2026-03-28

Amac
- city_controlled_flow_plan tablosuna gore 81 ilin her biri icin calisan primary marketi kos
- primary live degilse live fallback marketi sec
- sonucu dogrudan turkiye_market_platform.db icine yaz

Ana komut
- python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py

Faydalı varyantlar
- Sadece belirli asama:
  python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py --only-stage verified_local_needs_adapter
- Belirli sehirden itibaren devam:
  python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py --from-city kocaeli
- Deneme modu icin limit:
  python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py --limit 10
- Son 6 saatte basarili kosu varsa atla:
  python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py --skip-fresh-hours 6
- Primary'den sonra live fallback'i de kos:
  python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py --include-secondary-live

Ne yapiyor
- once bootstrap_nationwide mantigiyla DB ve rollout planini gunceller
- sonra her sehir icin uygun live marketi secer
- her run sonunda scrape_runs, raw_products, offers ve canonical tablolarini doldurur
- ozet cikti olarak sehir bazli status, fetched ve stored sayilarini basar

Bugunku dogrulama
- Tam 81 il kosusu basariyla tamamlandi
- executed_run_count: 81
- success_count: 81
- failure_count: 0
- total_stored_count: 4286
