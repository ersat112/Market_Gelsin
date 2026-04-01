from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import sqlite3
import os
import requests
import shutil
import urllib3
import hashlib

# SSL uyarılarını kapat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MarketAvcisi:
    def __init__(self):
        self.resim_klasoru = "urun_gorselleri"
        self.session_skus = set() 
        
        if not os.path.exists(self.resim_klasoru):
            os.makedirs(self.resim_klasoru)

        # ==========================================
        # 🗺️ 1. MİGROS LİNK HARİTASI (MANUEL)
        # ==========================================
        self.migros_harita = [
            ("Meyve-Sebze", "https://www.migros.com.tr/meyve-sebze-c-2"),
            ("Et-Balık", "https://www.migros.com.tr/et-tavuk-balik-c-3"),
            ("Süt-Kahvaltılık", "https://www.migros.com.tr/sut-kahvaltilik-c-4"),
            ("Temel Gıda", "https://www.migros.com.tr/temel-gida-c-5"),
            ("Meze-Yemek", "https://www.migros.com.tr/meze-hazir-yemek-donuk-c-6"),
            ("Fırın-Pastane", "https://www.migros.com.tr/firin-pastane-c-7"),
            ("Dondurma", "https://www.migros.com.tr/dondurma-c-8"),
            ("Atıştırmalık", "https://www.migros.com.tr/atistirmalik-c-9"),
            ("İçecek", "https://www.migros.com.tr/icecek-c-10"),
            ("Deterjan-Temizlik", "https://www.migros.com.tr/deterjan-temizlik-c-11"),
            ("Kağıt-Kozmetik", "https://www.migros.com.tr/kagit-kozmetik-c-12"),
            ("Bebek", "https://www.migros.com.tr/bebek-c-13"),
            ("Ev-Yaşam", "https://www.migros.com.tr/ev-yasam-c-14")
        ]

        # ==========================================
        # 🗺️ 2. ŞOK LİNK HARİTASI (MANUEL)
        # ==========================================
        self.sok_harita = [
            ("Meyve-Sebze", "https://www.sokmarket.com.tr/meyve-ve-sebze-c-20"),
            ("Et-Tavuk", "https://www.sokmarket.com.tr/et-ve-tavuk-c-22"),
            ("Süt-Ürünleri", "https://www.sokmarket.com.tr/sut-ve-sut-urunleri-c-23"),
            ("Kahvaltılık", "https://www.sokmarket.com.tr/kahvaltilik-c-24"),
            ("Ekmek-Pastane", "https://www.sokmarket.com.tr/ekmek-ve-pastane-c-25"),
            ("Yemeklik-Malzemeler", "https://www.sokmarket.com.tr/yemeklik-malzemeler-c-26"),
            ("Atıştırmalıklar", "https://www.sokmarket.com.tr/atistirmaliklar-c-27"),
            ("İçecekler", "https://www.sokmarket.com.tr/icecekler-c-28"),
            ("Kişisel-Bakım", "https://www.sokmarket.com.tr/kisisel-bakim-ve-kozmetik-c-31"),
            ("Temizlik", "https://www.sokmarket.com.tr/temizlik-c-30"),
            ("Kağıt-Ürünleri", "https://www.sokmarket.com.tr/kagit-urunleri-c-29"),
            ("Bebek-Oyuncak", "https://www.sokmarket.com.tr/anne-bebek-ve-cocuk-c-33")
        ]

    def db_baglan(self, market_adi):
        conn = sqlite3.connect(f"{market_adi}.db")
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS urunler 
                         (sku TEXT PRIMARY KEY, urun_adi TEXT, fiyat REAL, gorsel TEXT, kategori TEXT, tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        return conn

    def temiz_fiyat(self, text):
        if not text: return 0.0
        try:
            text = text.lower().replace('tl', '').replace('₺', '').strip()
            if "," in text: text = text.replace('.', '').replace(',', '.')
            return float(text)
        except: return 0.0

    def resim_indir(self, url, sku):
        if not url or "http" not in url: return "no_image.png"
        uzanti = "png" if ".png" in url else "jpg"
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

    def veri_kaydet(self, conn, ad, market, fiyat, img_url, kategori):
        if not ad or fiyat <= 0 or "stok" in ad.lower(): return False

        raw_id = f"{market}_{ad}".encode('utf-8')
        sku = hashlib.md5(raw_id).hexdigest()[:12]

        if sku in self.session_skus: return False
        self.session_skus.add(sku)

        local_img = self.resim_indir(img_url, sku)

        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO urunler (sku, urun_adi, fiyat, gorsel, kategori) VALUES (?, ?, ?, ?, ?)", 
                           (sku, ad, fiyat, local_img, kategori))
            conn.commit()
            print(f"   💾 {kategori}: {ad[:25]}... -> {fiyat} TL")
            return True
        except: return False

    def scroll_yap(self, page, miktar=3):
        for _ in range(miktar):
            page.mouse.wheel(0, 1000)
            time.sleep(1)

    # ==========================================
    # 🛒 MARKET TARAMA MOTORLARI
    # ==========================================

    def sok_motoru(self, page):
        print(f"\n🟡 ŞOK HARİTADAN TARANIYOR ({len(self.sok_harita)} Kategori)...")
        conn = self.db_baglan("Sok")
        self.session_skus.clear()

        for kat_adi, url in self.sok_harita:
            try:
                print(f"   ➡️ Kategoriye Giriliyor: {kat_adi}")
                page.goto(url, timeout=60000)
                time.sleep(3)
                self.scroll_yap(page, 10) # Şok tek sayfada yükler, bol scroll lazım

                soup = BeautifulSoup(page.content(), 'html.parser')
                kartlar = soup.select("div[class*='CProductCard'], div[class*='product-box']")
                
                sayac = 0
                for kart in kartlar:
                    try:
                        ad = kart.select_one("h2, .content-title, div[class*='title']").get_text(strip=True)
                        fiyat = kart.select_one("div[class*='PriceBox'], span[class*='price']").get_text(strip=True)
                        img = kart.select_one("img")['src']
                        if self.veri_kaydet(conn, ad, "Sok", self.temiz_fiyat(fiyat), img, kat_adi):
                            sayac += 1
                    except: continue
                print(f"      ✅ {sayac} ürün alındı.")
            except Exception as e: print(f"      ⚠️ Hata: {e}")
        conn.close()

    def migros_motoru(self, page):
        print(f"\n🟠 MİGROS HARİTADAN TARANIYOR ({len(self.migros_harita)} Kategori)...")
        conn = self.db_baglan("Migros")
        self.session_skus.clear()
        MAX_SAYFA = 3 # Her kategori için kaç sayfa gezilecek?

        for kat_adi, base_url in self.migros_harita:
            print(f"   ➡️ Kategori: {kat_adi}")
            for i in range(1, MAX_SAYFA + 1):
                try:
                    url = f"{base_url}?sayfa={i}" if i > 1 else base_url
                    page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(3)
                    
                    # Popup Temizleyici
                    try: 
                        page.mouse.click(10, 10)
                        page.keyboard.press("Escape")
                    except: pass
                    
                    self.scroll_yap(page, 4)
                    
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    kartlar = soup.select("mat-card, fe-product-card, sm-list-page-item, .product-card")
                    
                    if not kartlar: break 

                    sayac = 0
                    for kart in kartlar:
                        try:
                            ad = kart.select_one(".product-name, .mat-caption").get_text(strip=True)
                            fiyat = kart.select_one(".amount, .sale-price, .price").get_text(strip=True)
                            img_tag = kart.select_one("img")
                            img = img_tag['src'] if img_tag else ""
                            if self.veri_kaydet(conn, ad, "Migros", self.temiz_fiyat(fiyat), img, kat_adi):
                                sayac += 1
                        except: continue
                    print(f"      📄 Sayfa {i}: {sayac} ürün.")
                except: break
        conn.close()

    def mismar_motoru(self, page):
        # Mismar zaten çok temiz çalıştığı için onun "Otomatik Keşif" özelliğini korudum
        print(f"\n🟢 MİSMAR TARANIYOR (Otomatik)...")
        conn = self.db_baglan("Mismar")
        try:
            page.goto("https://www.mismarsanalmarket.com/", timeout=60000)
            time.sleep(2)
            
            # Linkleri topla
            hrefs = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('.menu-item a, .navigation a'))
                    .map(a => a.href).filter(h => h.includes('https') && !h.includes('iletisim'));
            }""")
            
            links = list(set(hrefs)) # Tekrarları sil
            
            for url in links:
                kat_adi = url.split("/")[-1].replace("-", " ").title()
                print(f"   ➡️ {kat_adi}")
                try:
                    page.goto(url, timeout=45000)
                    time.sleep(2)
                    self.scroll_yap(page, 4)
                    
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    kartlar = soup.select(".product-item, .ProductCard")
                    for kart in kartlar:
                        try:
                            ad = kart.select_one(".product-title").get_text(strip=True)
                            fiyat = kart.select_one(".current-price").get_text(strip=True)
                            img = "https://www.mismarsanalmarket.com" + kart.select_one("img")['src']
                            self.veri_kaydet(conn, ad, "Mismar", self.temiz_fiyat(fiyat), img, kat_adi)
                        except: continue
                except: continue
        except: pass
        conn.close()

    def baslat(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()

            # SIRASIYLA HEPSİNİ ÇALIŞTIR
            self.mismar_motoru(page)
            self.sok_motoru(page)
            self.migros_motoru(page)

            print("\n🏁 TÜM MARKETLERİN HARİTASI TAMAMLANDI.")
            browser.close()

if __name__ == "__main__":
    MarketAvcisi().baslat()