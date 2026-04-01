from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import sqlite3
import os
import requests
import shutil
import urllib3
import hashlib
import random

# SSL uyarılarını kapat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MarketAvcisi:
    def __init__(self):
        self.db_yolu = "konya_market_verisi.db"
        self.resim_klasoru = "urun_gorselleri"
        self.session_skus = set() 
        
        if not os.path.exists(self.resim_klasoru):
            os.makedirs(self.resim_klasoru)

        self.db_hazirla()

        # --- KATEGORİ LİSTELERİ (Buraya istediğini ekleyebilirsin) ---
        self.mismar_linkleri = [
            ("Meyve-Sebze", "https://www.mismarsanalmarket.com/meyve-sebze"),
            ("Et-Tavuk", "https://www.mismarsanalmarket.com/et-balik"),
            ("Süt-Kahvaltı", "https://www.mismarsanalmarket.com/sarkuteri-kahvaltilik"),
            ("Temel Gıda", "https://www.mismarsanalmarket.com/gida-sekerleme")
        ]

        self.sok_linkleri = [
            ("Meyve-Sebze", "https://www.sokmarket.com.tr/meyve-ve-sebze-c-20"),
            ("Et-Tavuk", "https://www.sokmarket.com.tr/et-ve-tavuk-c-22"),
            ("Süt-Kahvaltı", "https://www.sokmarket.com.tr/sut-ve-sut-urunleri-c-23"),
            ("Temel Gıda", "https://www.sokmarket.com.tr/temel-gida-c-26")
        ]

        self.migros_linkleri = [
            ("Meyve-Sebze", "https://www.migros.com.tr/meyve-sebze-c-2"),
            ("Et-Tavuk", "https://www.migros.com.tr/et-tavuk-balik-c-3"),
            ("Süt-Kahvaltı", "https://www.migros.com.tr/sut-kahvaltilik-c-4"),
            ("Temel Gıda", "https://www.migros.com.tr/temel-gida-c-5")
        ]

    def db_hazirla(self):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS urunler 
                         (sku TEXT PRIMARY KEY, urun_adi TEXT, market TEXT, 
                          fiyat REAL, gorsel TEXT, kategori TEXT, tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()

    def temiz_fiyat(self, text):
        if not text: return 0.0
        try:
            text = text.lower().replace('tl', '').replace('₺', '').strip()
            if "," in text:
                text = text.replace('.', '').replace(',', '.') # 29,90 -> 29.90
            return float(text)
        except: return 0.0

    def resim_indir(self, url, sku):
        if not url or "http" not in url: return "no_image.png"
        
        uzanti = "jpg"
        if ".png" in url: uzanti = "png"
        dosya_adi = f"{self.resim_klasoru}/{sku}.{uzanti}"
        
        if os.path.exists(dosya_adi): return dosya_adi

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, stream=True, verify=False, timeout=4)
            if r.status_code == 200:
                with open(dosya_adi, 'wb') as f:
                    r.raw.decode_content = True
                    shutil.copyfileobj(r.raw, f)
                return dosya_adi
        except: pass
        return "no_image.png"

    def veri_kaydet(self, ad, market, fiyat, img_url, kategori):
        if not ad or fiyat <= 0: return False
        
        # Mismar bazen "Stokta Yok" ürünlerin fiyatını 0 veya gizli verebilir
        if "stok" in ad.lower(): return False

        raw_id = f"{market}_{ad}".encode('utf-8')
        sku = hashlib.md5(raw_id).hexdigest()[:12]

        if sku in self.session_skus: return False
        self.session_skus.add(sku)

        local_img = self.resim_indir(img_url, sku)

        try:
            with sqlite3.connect(self.db_yolu, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO urunler (sku, urun_adi, market, fiyat, gorsel, kategori) VALUES (?, ?, ?, ?, ?, ?)", 
                               (sku, ad, market, fiyat, local_img, kategori))
                conn.commit()
            print(f"   💾 {market} [{kategori}]: {ad[:20]}... -> {fiyat} TL")
            return True
        except: return False

    def scroll_yap(self, page, miktar=3):
        for _ in range(miktar):
            page.mouse.wheel(0, 1000)
            time.sleep(1)

    # --- MARKET FONKSİYONLARI ---

    def mismar_tara(self, page):
        print("\n🟢 MİSMAR Taranıyor...")
        for kat_adi, url in self.mismar_linkleri:
            try:
                print(f"   ➡️ Kategori: {kat_adi}")
                page.goto(url, timeout=60000)
                time.sleep(3)
                self.scroll_yap(page, 5) # Mismar tek sayfada çok ürün gösterir

                soup = BeautifulSoup(page.content(), 'html.parser')
                kartlar = soup.select(".product-item, .ProductCard")

                for kart in kartlar:
                    try:
                        ad = kart.select_one(".product-title, .name").get_text(strip=True)
                        fiyat_txt = kart.select_one(".current-price, .price").get_text(strip=True)
                        
                        img_tag = kart.select_one("img")
                        img_url = ""
                        if img_tag:
                            img_url = img_tag.get('src') or img_tag.get('data-src')
                            if img_url and img_url.startswith("/"):
                                img_url = "https://www.mismarsanalmarket.com" + img_url

                        self.veri_kaydet(ad, "Mismar", self.temiz_fiyat(fiyat_txt), img_url, kat_adi)
                    except: continue
            except Exception as e: print(f"   ⚠️ Hata: {e}")

    def sok_tara(self, page):
        print("\n🟡 ŞOK Taranıyor...")
        for kat_adi, url in self.sok_linkleri:
            try:
                print(f"   ➡️ Kategori: {kat_adi}")
                page.goto(url, timeout=60000)
                time.sleep(3)
                self.scroll_yap(page, 8) # Şok çok ürün yükler, iyi scroll lazım

                soup = BeautifulSoup(page.content(), 'html.parser')
                kartlar = soup.select("div[class*='CProductCard'], div[class*='product-box']")

                for kart in kartlar:
                    try:
                        ad = kart.select_one("h2, .content-title, div[class*='title']").get_text(strip=True)
                        fiyat_txt = kart.select_one("div[class*='PriceBox'], span[class*='price']").get_text(strip=True)
                        img_tag = kart.select_one("img")
                        img_url = img_tag['src'] if img_tag else ""
                        self.veri_kaydet(ad, "Şok", self.temiz_fiyat(fiyat_txt), img_url, kat_adi)
                    except: continue
            except Exception as e: print(f"   ⚠️ Hata: {e}")

    def migros_tara(self, page):
        print("\n🟠 MİGROS Taranıyor (Sayfalı Mod)...")
        # Migros'ta her kategori için ilk 3 sayfayı gezelim
        MAX_SAYFA = 3 

        for kat_adi, base_url in self.migros_linkleri:
            print(f"   ➡️ Kategori: {kat_adi}")
            
            for i in range(1, MAX_SAYFA + 1):
                try:
                    # Sayfa URL mantığı: ?sayfa=2
                    if i == 1: current_url = base_url
                    else: current_url = f"{base_url}?sayfa={i}"
                    
                    print(f"      📄 Sayfa {i} taranıyor...")
                    page.goto(current_url, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(4) 
                    
                    # Popup temizliği (Sadece ilk sayfada gerekebilir ama her turda deneyelim)
                    try:
                        page.mouse.click(10, 10)
                        page.keyboard.press("Escape")
                    except: pass

                    self.scroll_yap(page, 3)

                    soup = BeautifulSoup(page.content(), 'html.parser')
                    kartlar = soup.select("mat-card, fe-product-card, sm-list-page-item, .product-card")
                    
                    if not kartlar:
                        print("      ⚠️ Bu sayfada ürün yok veya bitti.")
                        break # Ürün yoksa diğer sayfaları deneme, sonraki kategoriye geç

                    for kart in kartlar:
                        try:
                            ad = kart.select_one(".product-name, .mat-caption, a[href*='-p-']").get_text(strip=True)
                            fiyat_tag = kart.select_one(".amount, .sale-price, .price")
                            if not fiyat_tag: continue
                            
                            img_tag = kart.select_one("img")
                            img_url = img_tag['src'] if img_tag else ""
                            
                            self.veri_kaydet(ad, "Migros", self.temiz_fiyat(fiyat_tag.get_text(strip=True)), img_url, kat_adi)
                        except: continue
                except Exception as e: 
                    print(f"   ⚠️ Sayfa hatası: {e}")
                    break

    def baslat(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False, 
                args=["--disable-blink-features=AutomationControlled"] 
            )
            context = browser.new_context(
                # Desktop görünümü zorla ki sayfa numaraları çıksın
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080} 
            )
            page = context.new_page()

            # Tüm marketleri sırayla çağır
            self.mismar_tara(page)
            self.sok_tara(page)
            self.migros_tara(page)

            print("\n🏁 Tüm marketler ve kategoriler tarandı.")
            time.sleep(2)
            browser.close()

if __name__ == "__main__":
    MarketAvcisi().baslat()