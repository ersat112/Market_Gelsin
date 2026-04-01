from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import sqlite3
import os
import requests
import shutil
import urllib3
import hashlib
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("ManavAvcisi")

class ManavAvcisi:
    def __init__(self):
        self.db_yolu = "manav_verisi.db"
        self.resim_klasoru = "manav_gorselleri"
        self.hata_klasoru = "hata_resimleri" # Botun takıldığı yerleri görmek için
        self.session_skus = set() 
        
        for klasor in [self.resim_klasoru, self.hata_klasoru]:
            if not os.path.exists(klasor):
                os.makedirs(klasor)

        self.db_hazirla()

        self.marketler = [
            # Linki güncellenen Şehzade
            {"il": "Kayseri", "market": "Şehzade", "url": "https://sehzadeonline.com/manav-c-1", "tur": "sayfali"},
            {"il": "Ankara", "market": "Yunus Market", "url": "https://www.yunusonline.com/meyve-sebze-2", "tur": "scroll"},
            {"il": "Türkiye Geneli", "market": "CarrefourSA", "url": "https://www.carrefoursa.com/meyve-sebze/c/1014", "tur": "scroll"},
            {"il": "Konya", "market": "Mismar", "url": "https://www.mismarsanalmarket.com/meyve-sebze", "tur": "scroll"},
        ]

    def db_hazirla(self):
        with sqlite3.connect(self.db_yolu) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS manav_urunleri 
                             (sku TEXT PRIMARY KEY, il TEXT, market TEXT, urun_adi TEXT,  
                              fiyat REAL, gorsel TEXT, tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()

    def temiz_fiyat(self, text):
        if not text: return 0.0
        try:
            text = text.lower().replace('tl', '').replace('₺', '').strip()
            if "," in text:
                text = text.replace('.', '').replace(',', '.')
            return float(text)
        except Exception: return 0.0

    def veri_kaydet(self, il, market, ad, fiyat, img_url):
        if not ad or fiyat <= 0: return False
        
        raw_id = f"{il}_{market}_{ad}".encode('utf-8')
        sku = hashlib.md5(raw_id).hexdigest()[:12]

        if sku in self.session_skus: return False
        self.session_skus.add(sku)

        try:
            with sqlite3.connect(self.db_yolu, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO manav_urunleri (sku, il, market, urun_adi, fiyat, gorsel) VALUES (?, ?, ?, ?, ?, ?)", 
                               (sku, il, market, ad, fiyat, img_url))
                conn.commit()
            logger.info(f"[{il}] {market}: {ad[:25]:<25} -> {fiyat} TL")
            return True
        except Exception: return False

    def parse_sayfa(self, html, il, market):
        soup = BeautifulSoup(html, 'html.parser')
        
        # Genişletilmiş CSS Seçicileri (Eğer site güncellendiyse alternatifleri dener)
        selectors = {
            "CarrefourSA": {"kart": ".product-listing-item, .product-card", "ad": ".item-name, .product-name", "fiyat": ".item-price, .price"},
            "Mismar": {"kart": ".product-item, .ProductCard", "ad": ".product-title, .name", "fiyat": ".current-price, .price"},
            "Yunus Market": {"kart": ".product-item", "ad": ".product-title", "fiyat": ".current-price"},
            "Şehzade": {"kart": ".product-item", "ad": ".product-title, .name", "fiyat": ".current-price, .price"}
        }

        sel = selectors.get(market, selectors["Mismar"]) 
        kartlar = soup.select(sel["kart"])
        
        bulunan = 0
        for kart in kartlar:
            try:
                ad_tag = kart.select_one(sel["ad"])
                fiyat_tag = kart.select_one(sel["fiyat"])
                
                if not ad_tag or not fiyat_tag: continue
                
                ad = ad_tag.get_text(strip=True)
                fiyat = self.temiz_fiyat(fiyat_tag.get_text(strip=True))
                
                if self.veri_kaydet(il, market, ad, fiyat, ""):
                    bulunan += 1
            except Exception: continue
                
        return bulunan

    def market_tara(self, page, config):
        il, market, url, tur = config["il"], config["market"], config["url"], config["tur"]
        logger.info(f"--- TARANIYOR: {market} ({il}) ---")
        
        try:
            # Yunus Market gibi 403 veren siteler için ekstra bekleme ve gezinme süsü veriyoruz
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)
            
            # Sayfayı yavaşça aşağı kaydır (Resimlerin ve ürünlerin yüklenmesi için)
            for _ in range(5):
                page.mouse.wheel(0, 1000)
                time.sleep(1)

            bulunan = self.parse_sayfa(page.content(), il, market)
            
            # 🛑 EĞER 0 ÜRÜN BULUNURSA EKRAN GÖRÜNTÜSÜ AL (DEBUG)
            if bulunan == 0:
                hata_dosyasi = f"{self.hata_klasoru}/debug_{market}.png"
                page.screenshot(path=hata_dosyasi, full_page=True)
                logger.warning(f"⚠️ {market} 0 ürün döndürdü! Sayfa görüntüsü kaydedildi: {hata_dosyasi}")
            else:
                logger.info(f"Bitti: {market} - {bulunan} ürün bulundu.")
                
        except Exception as e:
            logger.error(f"{market} tarama başarısız (Muhtemelen 403 veya Zaman Aşımı): {e}")

    def baslat(self):
        logger.info("Manav Avcısı başlatılıyor...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False, # Ekranda ne olduğunu senin de görmen için False kalmalı
                args=["--disable-blink-features=AutomationControlled"] 
            )
            # Daha insansı bir cihaz kimliği (User-Agent) tanımlıyoruz
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                extra_http_headers={
                    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Sec-Ch-Ua": "\"Chromium\";v=\"122\", \"Not(A:Brand\";v=\"24\", \"Google Chrome\";v=\"122\""
                }
            )
            page = context.new_page()

            for market_ayar in self.marketler:
                self.market_tara(page, market_ayar)

            logger.info("Tüm market taramaları tamamlandı.")
            time.sleep(2)
            browser.close()

if __name__ == "__main__":
    avci = ManavAvcisi()
    avci.baslat()