import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import concurrent.futures
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TurboMigros:
    def __init__(self):
        self.db_yolu = "market_verisi.db"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.migros.com.tr/"
        }
        self.db_hazirla()

    def db_hazirla(self):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS urunler 
                         (sku TEXT PRIMARY KEY, urun_adi TEXT, market TEXT, fiyat REAL, gorsel TEXT, kategori TEXT)''')
        conn.commit()
        conn.close()

    def veri_kaydet(self, veri_listesi):
        if not veri_listesi: return
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        for urun in veri_listesi:
            sku = str(abs(hash(urun['ad'] + "Migros" + urun['kategori'])))[:12]
            cursor.execute("INSERT OR REPLACE INTO urunler VALUES (?, ?, ?, ?, ?, ?)",
                           (sku, urun['ad'], "Migros", urun['fiyat'], urun['img'], urun['kategori']))
        conn.commit()
        conn.close()
        print(f"🟠 Migros: {len(veri_listesi)} ürün kaydedildi.")

    def sitemap_getir(self):
        print("🟠 Migros Site Haritası Çekiliyor...")
        # Migros ürün haritası
        url = "https://www.migros.com.tr/sitemap-products.xml"
        try:
            res = requests.get(url, headers=self.headers, verify=False, timeout=20)
            soup = BeautifulSoup(res.content, 'xml')
            linkler = [loc.text for loc in soup.find_all('loc') if "migros.com.tr" in loc.text]
            print(f"✅ Migros'ta {len(linkler)} ürün linki bulundu.")
            return linkler[:3000] # Hız için limit
        except Exception as e:
            print(f"❌ Migros Harita Hatası: {e}")
            return []

    def tekli_tarama(self, url):
        try:
            res = requests.get(url, headers=self.headers, verify=False, timeout=10)
            if res.status_code != 200: return None
            
            soup = BeautifulSoup(res.content, 'html.parser')
            
            # Migros HTML Yapısı (JSON aramaya gerek yok, HTML'de var)
            ad = soup.select_one('h1.product-name').get_text(strip=True)
            fiyat_text = soup.select_one('.product-price, .amount').get_text(strip=True)
            fiyat = float(re.sub(r'[^\d,.]', '', fiyat_text).replace(',', '.'))
            
            img = soup.select_one('#product-image')['src']
            kategori = "Genel" # Kategori breadcrumb'dan alınabilir ama hız için geçiyorum

            if ad and fiyat:
                return {'ad': ad, 'fiyat': fiyat, 'img': img, 'kategori': kategori}
            return None
        except: return None

    def calistir(self):
        linkler = self.sitemap_getir()
        print(f"🚀 Migros Turbo Motoru {len(linkler)} ürün için çalışıyor...")
        
        toplanan = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: # Migros hassastır, işçi sayısını 5 yaptık
            sonuclar = list(executor.map(self.tekli_tarama, linkler))
            for s in sonuclar:
                if s:
                    toplanan.append(s)
                    if len(toplanan) >= 50:
                        self.veri_kaydet(toplanan)
                        toplanan = []
        if toplanan: self.veri_kaydet(toplanan)
        print("🏁 Migros Tamamlandı!")

if __name__ == "__main__":
    TurboMigros().calistir()