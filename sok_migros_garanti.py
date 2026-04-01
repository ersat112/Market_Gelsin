from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import re
import sqlite3
import os

class GarantiBot:
    def __init__(self):
        self.db_yolu = "market_verisi.db"
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
            text = text.replace('₺', '').replace('TL', '').strip()
            return float(re.sub(r'[^\d,.]', '', text).replace(',', '.'))
        except: return 0.0

    def veri_kaydet(self, ad, market, fiyat, gorsel, kategori):
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            sku = str(abs(hash(ad + market + kategori)))[:12]
            cursor.execute("INSERT OR REPLACE INTO urunler VALUES (?, ?, ?, ?, ?, ?)",
                           (sku, ad, market, fiyat, gorsel, kategori))
            conn.commit()
            conn.close()
            return True
        except: return False

    def liste_oku(self, dosya_adi, yedek_liste):
        try:
            if os.path.exists(dosya_adi):
                with open(dosya_adi, "r", encoding="utf-8") as f:
                    content = f.read()
                    linkler = re.findall(r'"(https://.*?)"', content)
                    if linkler:
                        print(f"📂 {dosya_adi} dosyasından {len(linkler)} kategori yüklendi.")
                        return linkler
            return yedek_liste
        except: return yedek_liste

    def engelleri_kaldir(self, page):
        """Pop-up ve Çerez Temizleyici"""
        try:
            page.keyboard.press("Escape")
            
            # Tıklanabilir metinler
            butonlar = ["Tümünü Kabul Et", "Kabul Et", "Anladım", "Onayla", "Tamam"]
            for btn_text in butonlar:
                try:
                    t = page.get_by_text(btn_text, exact=True)
                    if t.is_visible(): t.click()
                except: pass

            # CSS ile silme
            page.evaluate("""() => {
                const selectors = [
                    '#onetrust-banner-sdk', '.banner-actions-container',
                    'div[class*="cookie"]', 'div[class*="overlay"]',
                    '.CButton-module_secondary__b-W9y'
                ];
                selectors.forEach(s => {
                    const el = document.querySelector(s);
                    if(el) el.remove();
                });
            }""")
        except: pass

    def baslat(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            # Listeleri Oku
            sok_kategoriler = self.liste_oku("sok_listesi.txt", ["https://www.sokmarket.com.tr/meyve-ve-sebze-c-20"])
            migros_kategoriler = self.liste_oku("migros_listesi.txt", ["https://www.migros.com.tr/meyve-sebze-c-2"])

            # --- TARAMA ---
            print(f"\n🟡 ŞOK MARKET: {len(sok_kategoriler)} kategori taranacak...")
            for url in sok_kategoriler:
                kat_adi = url.split("-c-")[0].split("/")[-1].replace("-", " ").title()
                self.sonsuz_tara(page, url, kat_adi, "Şok")

            print(f"\n🟠 MİGROS: {len(migros_kategoriler)} kategori taranacak...")
            for url in migros_kategoriler:
                kat_adi = url.split("-c-")[0].split("/")[-1].replace("-", " ").title()
                self.sonsuz_tara(page, url, kat_adi, "Migros")

            browser.close()

    def sonsuz_tara(self, page, url, kat_adi, market):
        try:
            print(f"   📦 {market} > {kat_adi} taranıyor...")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            self.engelleri_kaldir(page)

            last_height = page.evaluate("document.body.scrollHeight")
            toplam_urun = 0
            bos_donus_sayisi = 0 # Ürün bulamadan kaç kez scroll yaptık?

            # --- SONSUZ DÖNGÜ BAŞLIYOR ---
            while True:
                # 1. Mevcut ekrandaki ürünleri topla
                soup = BeautifulSoup(page.content(), 'html.parser')
                
                # Fiyat etiketi içeren kutuları bul (Class bağımsız yöntem)
                # Hem Şok hem Migros için genel tarama
                if market == "Şok":
                    aday_kartlar = soup.find_all("div", class_=True)
                else:
                    aday_kartlar = soup.select('mat-card, .product-card, sm-list-page-item')

                sayfa_urun_sayisi = 0
                for kart in aday_kartlar:
                    try:
                        text = kart.get_text()
                        # Fiyat kontrolü (₺ veya ,00 içerenler)
                        fiyat_match = re.search(r'(\d{1,3}[.,]\d{2})\s*(?:TL|₺)?', text)
                        if not fiyat_match: continue
                        
                        fiyat = self.temiz_fiyat(fiyat_match.group(1))
                        if fiyat <= 0: continue

                        # İsim bulma
                        ad = ""
                        ad_tag = kart.select_one('h2, h3, .product-title, .name, strong')
                        if ad_tag: ad = ad_tag.get_text(strip=True)
                        else:
                            img_t = kart.select_one('img')
                            if img_t: ad = img_t.get('alt')
                        
                        if not ad or len(ad) < 3: continue

                        # Resim bulma
                        img = ""
                        img_tag = kart.select_one('img')
                        if img_tag:
                            img = img_tag.get('src')
                            if "loading" in str(img): img = img_tag.get('data-src') or img

                        # Kaydet
                        if self.veri_kaydet(ad, market, fiyat, img, kat_adi):
                            sayfa_urun_sayisi += 1

                    except: continue
                
                # 2. İstatistik Güncelle
                yeni_eklenen = sayfa_urun_sayisi # (Burada tam farkı bulmak zor ama akışın devam ettiğini görüyoruz)
                
                # 3. Akıllı Kaydırma (Scroll)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2) # Yüklenmesi için bekle
                
                # Biraz yukarı oynat (Tetiklemek için)
                page.mouse.wheel(0, -200)
                time.sleep(1)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

                new_height = page.evaluate("document.body.scrollHeight")
                
                # --- DURMA KOŞULLARI ---
                if new_height == last_height:
                    bos_donus_sayisi += 1
                    # 3 kere denedim, boy uzamadı, demek ki bitti.
                    if bos_donus_sayisi >= 3:
                        print(f"      🏁 Sayfa sonuna gelindi. (Yükseklik sabit)")
                        break
                else:
                    last_height = new_height
                    bos_donus_sayisi = 0 # Sayfa uzadı, sayacı sıfırla
                    print(f"      ⬇️ Kaydırıldı... (Toplam tarama devam ediyor)")

                # Pop-up temizliği (Her scroll'da tekrarla)
                self.engelleri_kaldir(page)

            print(f"   ✅ {market} > {kat_adi} tamamlandı.")

        except Exception as e:
            print(f"   ⚠️ Hata: {e}")

if __name__ == "__main__":
    GarantiBot().baslat()