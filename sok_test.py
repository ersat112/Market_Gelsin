from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

def sok_rontgen():
    with sync_playwright() as p:
        # Tarayıcıyı görünür modda açıyoruz ki ne yaptığını görelim
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        print("🕵️‍♂️ Şok Market Dedektifi iş başında...")
        
        # Doğrudan arama sayfasına gidiyoruz
        url = "https://www.sokmarket.com.tr/arama?q=Ayçiçek Yağı"
        page.goto(url, wait_until="domcontentloaded")
        
        # 1. Çerez ve Engel Geçme
        try:
            print("⏳ Sayfa yükleniyor...")
            page.wait_for_timeout(3000) # Biraz bekle
            
            # Çerez butonu varsa tıkla
            if page.is_visible("#onetrust-accept-btn-handler"):
                page.click("#onetrust-accept-btn-handler")
                print("✅ Çerezler kabul edildi.")
            else:
                print("ℹ️ Çerez butonu görünmedi.")
                
        except Exception as e:
            print(f"⚠️ Engel geçme uyarısı: {e}")

        # 2. Ürünlerin yüklenmesini bekle ve aşağı kaydır
        print("⏳ Ürünler taranıyor (5 saniye)...")
        time.sleep(5)
        page.mouse.wheel(0, 500)
        time.sleep(2)
        
        # 3. HTML Analizi
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Şok'un olası kutu isimlerini geniş tarıyoruz
        # Class isminde 'ProductCard' geçen, 'CepteSok' geçen veya link yapısı ürün olanları al
        kutular = soup.select("div[class*='ProductCard'], .CepteSok-ProductCard, .product-item-wrapper, a[href*='/urun/']")
        
        print(f"\n🔍 Analiz Sonucu: {len(kutular)} adet potansiyel ürün kutusu bulundu.")
        
        if len(kutular) > 0:
            print("\n" + "="*50)
            print("📢 AŞAĞIDAKİ KODU KOPYALA VE BANA YAPIŞTIR:")
            print("="*50 + "\n")
            
            # İlk kutunun HTML kodunu yazdır
            # (Sadece ilk 1000 karakteri alalım ki terminali kilitlemesin, ama kritik yerler görünsün)
            print(kutular[0].prettify())
            
            print("\n" + "="*50)
        else:
            print("❌ HATA: Hiçbir kutu yakalanamadı. Şok tamamen yapı değiştirmiş olabilir.")
            
        browser.close()

if __name__ == "__main__":
    sok_rontgen()