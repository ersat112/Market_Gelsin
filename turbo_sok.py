import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import concurrent.futures
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TurboSok:
    def __init__(self):
        self.db_yolu = "market_verisi.db"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": "https://www.sokmarket.com.tr/"
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
            sku = str(abs(hash(urun['ad'] + "Şok" + urun['kategori'])))[:12]
            cursor.execute("INSERT OR REPLACE INTO urunler VALUES (?, ?, ?, ?, ?, ?)",
                           (sku, urun['ad'], "Şok", urun['fiyat'], urun['img'], urun['kategori']))
        conn.commit()
        conn.close()
        print(f"🟡 Şok: {len(veri_listesi)} ürün kaydedildi.")

    def sitemap_getir(self):
        print("🟡 Şok Site Haritası Çekiliyor...")
        # Şok'un ürün sitemap'i
        url = "https://www.sokmarket.com.tr/sitemap/products.xml" 
        try:
            res = requests.get(url, headers=self.headers, verify=False, timeout=20)
            soup = BeautifulSoup(res.content, 'xml')
            linkler = [loc.text for loc in soup.find_all('loc')]
            print(f"✅ Şok'ta {len(linkler)} ürün linki bulundu.")
            return linkler[:3000] # Hepsini alırsak çok sürer, şimdilik 3000 limit koydum
        except Exception as e:
            print(f"❌ Şok Harita Hatası: {e}")
            return []

    def tekli_tarama(self, url):
        try:
            res = requests.get(url, headers=self.headers, verify=False, timeout=10)
            if res.status_code != 200: return None
            
            # Şok, veriyi HTML içinde gizli bir JSON (Next.js) olarak tutar.
            soup = BeautifulSoup(res.content, 'html.parser')
            next_data = soup.find("script", {"id": "__NEXT_DATA__"})
            
            if next_data:
                data = json.loads(next_data.string)
                props = data['props']['pageProps']['product']
                
                ad = props.get('name')
                fiyat = props.get('price', {}).get('salesPrice', 0)
                if not fiyat: fiyat = props.get('salesPrice', 0)
                
                img = props.get('images', [{}])[0].get('url', '')
                if img: img = f"https://cdnd-tr.sokmarket.com.tr/{img}"
                
                # Kategori yolu
                kategori = "Genel"
                try: kategori = props.get('category', {}).get('name', 'Genel')
                except: pass

                if ad and fiyat:
                    return {'ad': ad, 'fiyat': float(fiyat), 'img': img, 'kategori': kategori}
            return None
        except: return None

    def calistir(self):
        linkler = self.sitemap_getir()
        print(f"🚀 Şok Turbo Motoru {len(linkler)} ürün için çalışıyor...")
        
        toplanan = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            sonuclar = list(executor.map(self.tekli_tarama, linkler))
            for s in sonuclar:
                if s:
                    toplanan.append(s)
                    if len(toplanan) >= 50:
                        self.veri_kaydet(toplanan)
                        toplanan = []
        if toplanan: self.veri_kaydet(toplanan)
        print("🏁 Şok Tamamlandı!")

if __name__ == "__main__":
    TurboSok().calistir()