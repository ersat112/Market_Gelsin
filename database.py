import sqlite3
from datetime import datetime
import os

class MarketDB:
    def __init__(self, db_name='market_verisi.db'):
        self.db_name = db_name
        self.tabloyu_kur()

    def baglanti_al(self):
        return sqlite3.connect(self.db_name)

    def tabloyu_kur(self):
        try:
            with self.baglanti_al() as conn:
                cursor = conn.cursor()
                # 'kategori' sütunu EKLENDİ
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS urunler (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sku TEXT,
                        urun_adi TEXT,
                        market TEXT,
                        fiyat REAL,
                        gorsel TEXT,
                        kategori TEXT, 
                        tarih TEXT
                    )
                ''')
                conn.commit()
        except Exception as e:
            print(f"❌ Tablo Hatası: {e}")

    def veri_ekle(self, sku, urun_adi, market, fiyat, gorsel_url, kategori):
        try:
            with self.baglanti_al() as conn:
                cursor = conn.cursor()
                tarih = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # Kategori verisini de kaydediyoruz
                cursor.execute('''
                    INSERT INTO urunler (sku, urun_adi, market, fiyat, gorsel, kategori, tarih)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (sku, urun_adi, market, float(fiyat), gorsel_url, kategori, tarih))
                conn.commit()
        except Exception as e:
            print(f"❌ DB Yazma Hatası: {e}")