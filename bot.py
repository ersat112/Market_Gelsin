from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import re
import sqlite3

class DerinMarketSupurucu:

    def __init__(self):
        self.db_yolu = "market_verisi.db"
        self.db_hazirla()

    def db_hazirla(self):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS urunler (
            sku TEXT PRIMARY KEY,
            urun_adi TEXT,
            market TEXT,
            fiyat REAL,
            gorsel TEXT,
            kategori TEXT
        )
        """)
        conn.commit()
        conn.close()

    def temiz_fiyat(self, text):
        try:
            return float(re.sub(r"[^\d,\.]", "", text).replace(",", "."))
        except:
            return 0.0

    def veri_kaydet(self, ad, market, fiyat, gorsel, kategori):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        sku = str(abs(hash(ad + market + kategori)))[:12]
        cursor.execute("""
            INSERT OR REPLACE INTO urunler 
            (sku, urun_adi, market, fiyat, gorsel, kategori)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sku, ad, market, fiyat, gorsel, kategori))
        conn.commit()
        conn.close()

    def sonsuza_kadar_scroll(self, page, urun_selector, max_tur=200):
        print("   ⬇️ Scroll başlıyor...")
        onceki_yukseklik = page.evaluate("document.body.scrollHeight")
        ayni_sayac = 0

        for tur in range(max_tur):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(1.5)

            yeni_yukseklik = page.evaluate("document.body.scrollHeight")
            mevcut_urun = len(page.query_selector_all(urun_selector))

            print(f"      tur {tur+1} | ürün: {mevcut_urun}")

            if yeni_yukseklik == onceki_yukseklik:
                ayni_sayac += 1
            else:
                ayni_sayac = 0

            onceki_yukseklik = yeni_yukseklik

            if ayni_sayac >= 5:
                print("   🛑 Yeni ürün gelmiyor, duruldu.")
                break

    def supur(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.set_default_timeout(90000)

            print("🔍 ŞOK Kategoriler...")
            page.goto("https://www.sokmarket.com.tr/", wait_until="domcontentloaded")
            time.sleep(5)

            try:
                if page.is_visible("#onetrust-accept-btn-handler"):
                    page.click("#onetrust-accept-btn-handler")
            except:
                pass

            sok_links = list(set([
                "https://www.sokmarket.com.tr" + a.get_attribute("href")
                for a in page.query_selector_all('a[href*="-c-"]')
                if a.get_attribute("href") and a.get_attribute("href").startswith("/")
            ]))

            print("🔍 MİSMAR Kategoriler...")
            page.goto("https://www.mismarsanalmarket.com/", wait_until="domcontentloaded")
            time.sleep(3)

            mismar_links = list(set([
                "https://www.mismarsanalmarket.com" + a.get_attribute("href")
                for a in page.query_selector_all('.menu-item a, .category-card a')
                if a.get_attribute("href")
            ]))

            print("🔍 MİGROS Kategoriler...")
            page.goto("https://www.migros.com.tr/", wait_until="domcontentloaded")
            time.sleep(5)

            migros_links = list(set([
                "https://www.migros.com.tr" + a.get_attribute("href")
                for a in page.query_selector_all('a[href*="-c-"]')
                if a.get_attribute("href") and "-c-" in a.get_attribute("href")
            ]))

            for kat in sok_links:
                kat_adi = kat.split("/")[-1].split("-c-")[0]
                self.reyon_kazi(page, "Şok", kat,
                                'div[class*="CProductCard-module_productCardWrapper"]',
                                'h2', 'span[class*="CPrice"]', 'img', kat_adi)

            for kat in mismar_links:
                kat_adi = kat.split("/")[-1]
                self.reyon_kazi(page, "Mismar", kat,
                                '.product-item', '.name', '.last-price', 'img', kat_adi)

            for kat in migros_links:
                kat_adi = kat.split("/")[-1].split("-c-")[0]
                self.reyon_kazi(page, "Migros", kat,
                                'mat-card', '.product-name', '.amount', 'img', kat_adi)

            browser.close()
            print("🏁 BİTTİ")

    def reyon_kazi(self, page, market, url, kutu, ad_et, fiyat_et, resim_et, kat_adi):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            if market == "Şok":
                try:
                    if page.is_visible("#onetrust-accept-btn-handler"):
                        page.click("#onetrust-accept-btn-handler")
                    page.keyboard.press("Escape")
                except:
                    pass

            print(f"📦 {market} > {kat_adi}")

            page.wait_for_selector(kutu, timeout=20000)
            self.sonsuza_kadar_scroll(page, kutu, max_tur=200)

            soup = BeautifulSoup(page.content(), "html.parser")
            urunler = soup.select(kutu)

            count = 0
            for urun in urunler:
                try:
                    ad_tag = urun.select_one(ad_et)
                    fiyat_tag = urun.select_one(fiyat_et)

                    if not ad_tag or not fiyat_tag:
                        continue

                    ad = ad_tag.get_text(strip=True)
                    fiyat = self.temiz_fiyat(fiyat_tag.get_text(strip=True))

                    img_tag = urun.select_one(resim_et)
                    img = ""
                    if img_tag:
                        img = img_tag.get("src") or img_tag.get("data-src") or ""

                    if market == "Mismar" and img.startswith("/"):
                        img = "https://www.mismarsanalmarket.com" + img

                    if ad and fiyat > 0:
                        self.veri_kaydet(ad, market, fiyat, img, kat_adi)
                        count += 1
                except:
                    continue

            print(f"   ➕ {count} ürün")

        except Exception as e:
            print(f"⚠️ {market} - {kat_adi} atlandı: {e}")


if __name__ == "__main__":
    DerinMarketSupurucu().supur()
