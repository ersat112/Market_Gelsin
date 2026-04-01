# Ulusal Market Oncelikleri

Bu fazda yerel marketlerden once ulke geneli hizmet veren veya yaygin ulusal kapsama sahip marketler onceliklenir.

## Cekirdek sira

1. `bim_market`
2. `a101_kapida`
3. `cepte_sok`
4. `migros_sanal_market`
5. `carrefoursa_online_market`
6. `tarim_kredi_koop_market`
7. `bizim_toptan_online`
8. `getir_buyuk`

## Neden bu sira

- Indirim zincirleri ve buyuk ulusal marketler en genis kapsami saglar.
- Bu marketler tamamlandiginda 81 il fallback kalitesi ciddi sekilde yukselir.
- API ve mobil uygulama katmani icin once bu zincirlerin veri modeli sabitlenmelidir.

## Komutlar

Ulusal oncelik listesini gormek:

```bash
python3 /Users/ersat/Desktop/Market_Gelsin/report_national_market_priority.py
```

Canli ulusal marketleri toplu kosmak:

```bash
python3 /Users/ersat/Desktop/Market_Gelsin/run_all_national_markets.py --city-limit 81
```

Sadece tek sehirde dogrulama kosusu:

```bash
python3 /Users/ersat/Desktop/Market_Gelsin/run_all_national_markets.py --city istanbul --city-limit 1
```
