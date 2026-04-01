import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import concurrent.futures
import time
import urllib3
import json

# SSL Uyarılarını Sustur
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TurboMismar:
    def __init__(self):
        self.db_yolu = "market_verisi.db"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.db_hazirla()

    def db_hazirla(self):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS urunler 
                         (sku TEXT PRIMARY KEY, urun_adi TEXT, market TEXT, fiyat REAL, gorsel TEXT, kategori TEXT)''')
        conn.commit()
        conn.close()

    def temiz_fiyat(self, text):
        try:
            return float(re.sub(r'[^\d,.]', '', text).replace(',', '.'))
        except: return 0.0

    def veri_kaydet(self, veri_listesi):
        if not veri_listesi: return
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        for urun in veri_listesi:
            sku = str(abs(hash(urun['ad'] + "Mismar" + urun['kategori'])))[:12]
            cursor.execute("INSERT OR REPLACE INTO urunler VALUES (?, ?, ?, ?, ?, ?)",
                           (sku, urun['ad'], "Mismar", urun['fiyat'], urun['img'], urun['kategori']))
        conn.commit()
        conn.close()
        print(f"💾 {len(veri_listesi)} Mismar ürünü kaydedildi.")

    def sitemap_getir(self):
        print("🗺️ Mismar Haritası İndiriliyor...")
        url = "https://www.mismarsanalmarket.com/sitemap.xml"
        try:
            res = requests.get(url, headers=self.headers, verify=False, timeout=15)
            try: soup = BeautifulSoup(res.content, 'xml')
            except: soup = BeautifulSoup(res.content, 'html.parser')
            
            linkler = [loc.text for loc in soup.find_all('loc')]
            temiz_linkler = [l for l in linkler if "mismarsanalmarket.com" in l and len(l.split('/')) > 3]
            
            print(f"✅ Haritada {len(temiz_linkler)} ürün bulundu.")
            return temiz_linkler
        except Exception as e:
            print(f"❌ Harita hatası: {e}")
            return []

    def tekli_tarama(self, url):
        try:
            res = requests.get(url, headers=self.headers, verify=False, timeout=10)
            if res.status_code != 200: return None
            
            soup = BeautifulSoup(res.content, 'html.parser')
            
            # --- İSİM VE FİYAT ---
            ad_tag = soup.select_one('h1.product-title, .product-name, h1')
            fiyat_tag = soup.select_one('.current-price, .price, .product-price, .last-price')
            
            if ad_tag and fiyat_tag:
                ad = ad_tag.get_text(strip=True)
                fiyat = self.temiz_fiyat(fiyat_tag.get_text(strip=True))
                
                # Kategori
                breadcrumb = soup.select('.breadcrumb li, .breadcrumb-item')
                kategori = breadcrumb[-2].get_text(strip=True) if breadcrumb and len(breadcrumb) > 1 else "Genel"

                # --- RESİM AVCILIĞI (Logo Filtreli) ---
                img = ""
                
                # 1. Yöntem: Meta Etiketleri (En temiz kaynak)
                meta_img = soup.find("meta", property="og:image")
                if meta_img: img = meta_img["content"]

                # 2. Yöntem: Ürün Görseli (HTML)
                if not img or "logo" in img or "placeholder" in img:
                    img_candidates = soup.select('.product-image img, .main-image img, img[itemprop="image"]')
                    for img_tag in img_candidates:
                        # Olası kaynakları dene
                        src = img_tag.get('data-original') or img_tag.get('data-src') or img_tag.get('src')
                        if src and "logo" not in src and "placeholder" not in src:
                            img = src
                            break
                
                # 3. Yöntem: JSON Verisi (Google için saklanan veri)
                if not img or "logo" in img:
                    scripts = soup.find_all('script', type='application/ld+json')
                    for script in scripts:
                        try:
                            data = json.loads(script.string)
                            # Bazen liste döner, bazen sözlük
                            if isinstance(data, list): data = data[0]
                            
                            if 'image' in data:
                                cand_img = data['image']
                                if isinstance(cand_img, list): cand_img = cand_img[0]
                                if "logo" not in cand_img:
                                    img = cand_img
                                    break
                        except: continue

                # URL Düzeltme
                if img and img.startswith("/"):
                    img = "https://www.mismarsanalmarket.com" + img
                
                # SON KONTROL: Hala logoysa veya boşsa, varsayılan bir ürün resmi koyabiliriz
                # Ama veritabanını kirletmemek için boş bırakmak daha iyidir.
                if "logo" in img.lower() or "no-image" in img.lower():
                    img = "" 

                if fiyat > 0:
                    return {'ad': ad, 'fiyat': fiyat, 'img': img, 'kategori': kategori}
            return None
        except:
            return None

    def motoru_calistir(self):
        linkler = self.sitemap_getir()
        
        # Test için manuel link ekleyebilirsin
        if not linkler:
            print("⚠️ Harita boş, manuel liste deneniyor...")
            linkler = ["https://www.mismarsanalmarket.com/et-balik-tavuk"]

        print(f"🚀 Turbo Motor {len(linkler)} ürün için çalışıyor...")
        
        toplanan_veriler = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            sonuclar = list(executor.map(self.tekli_tarama, linkler))
            
            for sonuc in sonuclar:
                if sonuc:
                    toplanan_veriler.append(sonuc)
                    
                    # Log kontrolü
                    durum = "🖼️" if sonuc['img'] else "🚫"
                    if "logo" in sonuc['img']: durum = "⚠️ LOGO"
                    
                    print(f"   {durum} {sonuc['ad']} - {sonuc['fiyat']} TL")
                
                if len(toplanan_veriler) >= 50:
                    self.veri_kaydet(toplanan_veriler)
                    toplanan_veriler = []

        if toplanan_veriler:
            self.veri_kaydet(toplanan_veriler)

        print("🏁 Mismar (Logosuz) Tamamlandı!")

if __name__ == "__main__":
    TurboMismar().motoru_calistir()