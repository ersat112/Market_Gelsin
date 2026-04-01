from playwright.sync_api import sync_playwright
import time

def ajan_calistir():
    with sync_playwright() as p:
        # Tarayıcıyı görünür yapalım ki ne yaptığını izle
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # ==========================================
        # 🟡 1. ŞOK MARKET KATEGORİ AVI
        # ==========================================
        print("\n🟡 ŞOK MARKET Taranıyor...")
        try:
            page.goto("https://www.sokmarket.com.tr/kategoriler", wait_until="domcontentloaded", timeout=60000)
            time.sleep(5) # Menülerin yüklenmesini bekle

            # Şok'ta kategoriler "-c-" ile biter, ürünler "-p-" ile biter.
            # Biz sadece -c- olanları alacağız.
            sok_linkleri = page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links
                        .map(a => a.href)
                        .filter(href => href.includes('-c-'))   // Kategori kodu
                        .filter(href => !href.includes('-p-'))  // Ürünleri ele
                        .filter(href => !href.includes('markalar')) // Marka sayfalarını ele
                        .filter(href => !href.includes('kampanyalar')); // Kampanyaları ele
                }
            """)
            
            sok_temiz = sorted(list(set(sok_linkleri))) # Tekrarları sil ve sırala
            print(f"✅ Şok'ta {len(sok_temiz)} adet alt kategori bulundu!")
            
            # Dosyaya Yaz (Kaybolmasın)
            with open("sok_listesi.txt", "w", encoding="utf-8") as f:
                f.write("sok_kategoriler = [\n")
                for link in sok_temiz:
                    f.write(f'    "{link}",\n')
                f.write("]\n")

        except Exception as e:
            print(f"❌ Şok hatası: {e}")

        # ==========================================
        # 🟠 2. MİGROS KATEGORİ AVI
        # ==========================================
        print("\n🟠 MİGROS Taranıyor...")
        try:
            page.goto("https://www.migros.com.tr/", wait_until="domcontentloaded", timeout=60000)
            
            # Çerezleri kabul et ki menüyü engellemesin
            try: page.click("#accept-all-cookies", timeout=3000)
            except: pass
            
            time.sleep(5) 

            # Migros'ta tüm kategoriler menüdedir, hepsini çekiyoruz
            migros_linkleri = page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links
                        .map(a => a.href)
                        .filter(href => href.includes('-c-')) // Migros kategori imzası
                        .filter(href => !href.includes('kampanya'))
                        .filter(href => href.startsWith('https://www.migros.com.tr'));
                }
            """)

            migros_temiz = sorted(list(set(migros_linkleri)))
            print(f"✅ Migros'ta {len(migros_temiz)} adet alt kategori bulundu!")

            # Dosyaya Yaz
            with open("migros_listesi.txt", "w", encoding="utf-8") as f:
                f.write("migros_kategoriler = [\n")
                for link in migros_temiz:
                    f.write(f'    "{link}",\n')
                f.write("]\n")

        except Exception as e:
            print(f"❌ Migros hatası: {e}")

        browser.close()
        print("\n🏁 İŞLEM TAMAM! 'sok_listesi.txt' ve 'migros_listesi.txt' dosyaları oluşturuldu.")

if __name__ == "__main__":
    ajan_calistir()