Kontrollu Canli Akis Yol Haritasi
Tarih: 2026-03-28

Hedef
- Faz 1: 81 ilin tamami icin en az bir markette calisan adapter + kontrollu veri akisi
- Faz 2: Ayni illerde kategori ve sayfa kapsamini genisleterek tam katalog akisina gecis

Kontrollu veri akisi ne demek
- Tam katalog zorunlu degil
- Limitli ama gercek urun, fiyat ve stok sinyali ureten adapter yeterli
- Sonraki adim tam katalog icin pagination, kategori genisletme ve cursor/checkpoint eklemek

Guncel durum
- live_controlled_local: 24 il
- verified_local_needs_adapter: 31 il
- discovery_pending_national_fallback: 26 il
- national_controlled_live: cepte_sok, tarim_kredi_koop_market, bizim_toptan_online
- Son eklenen canli yerel hatlar: onur_market_kirklareli, onur_market_tekirdag, showmar_istanbul, taso_market_kocaeli

Yonetim kurali
- Her il icin city_controlled_flow_plan tablosunda bir primary market key bulunur
- Yerel market dogrulanmissa once o markete kontrollu adapter yazilir
- Yerel market henuz dogrulanmadiysa gecici fallback olarak once Cepte Sok, ikinci hat olarak Migros kullanilir
- Faz 1 tamamlanmadan tam katalog refaktoru ana odak haline getirilmez

Yurutme sirasi
1. 31 verified_local_needs_adapter sehri canli kontrollu akisa cek
2. 26 discovery_pending sehri icin fallback akisi ac ve yerel kesfi surdur
3. Her sehirde ikinci market baglayarak karsilastirma kalitesini artir
4. Son asamada live marketlerde hard capleri kaldirip tam katalog moduna gec

Takip noktasi
- DB tablosu: city_controlled_flow_plan
- Rapor komutu: python3 /Users/ersat/Desktop/Market_Gelsin/report_controlled_flow_rollout.py
- Bootstrap: python3 /Users/ersat/Desktop/Market_Gelsin/bootstrap_nationwide.py
- Toplu 81 il cekimi: python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py
- Resume ornekleri:
  python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py --from-city kocaeli
  python3 /Users/ersat/Desktop/Market_Gelsin/run_all_cities_controlled_flow.py --only-stage verified_local_needs_adapter
