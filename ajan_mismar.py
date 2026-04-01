from playwright.sync_api import sync_playwright
import time

def mismar_ajan():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print("🕵️ Mismar Sanal Market Haritası Çıkarılıyor...")
        page.goto("https://www.mismarsanalmarket.com/", wait_until="domcontentloaded")
        time.sleep(5) # Menülerin yüklenmesi için bekle

        # Tüm linkleri topla ve temizle
        linkler = page.evaluate("""
            () => {
                const tum_linkler = Array.from(document.querySelectorAll('a'));
                return tum_linkler
                    .map(a => a.href)
                    .filter(href => href.includes('mismarsanalmarket.com')) // Sadece site içi
                    .filter(href => !href.includes('#')) // Boş linkleri at
                    .filter(href => !href.includes('javascript'))
                    // Gereksiz sayfaları temizle
                    .filter(href => !href.includes('sepet'))
                    .filter(href => !href.includes('giris'))
                    .filter(href => !href.includes('kayit'))
                    .filter(href => !href.includes('hesabim'))
                    .filter(href => !href.includes('odeme'))
                    .filter(href => !href.includes('hakkimizda'))
                    .filter(href => !href.includes('iletisim'))
                    .filter(href => !href.includes('yardim'))
                    .filter(href => !href.includes('whatsapp'))
                    .filter(href => !href.includes('instagram'))
                    .filter(href => !href.includes('facebook'));
            }
        """)

        # Linkleri temizle (Sadece kategori gibi duranları alalım)
        # Genelde kategori linkleri kısa ve temiz olur (örn: .com/meyve-sebze)
        temiz_liste = []
        for link in linkler:
            # Ana sayfa hariç, çok uzun parametreli linkler hariç
            if link != "https://www.mismarsanalmarket.com/" and len(link) < 80:
                temiz_liste.append(link)

        # Benzersiz yap ve sırala
        final_liste = sorted(list(set(temiz_liste)))
        
        print(f"✅ Toplam {len(final_liste)} kategori bulundu!")

        # Dosyaya Yaz
        dosya_adi = "mismar_listesi.txt"
        with open(dosya_adi, "w", encoding="utf-8") as f:
            f.write("mismar_listesi = [\n")
            for link in final_liste:
                f.write(f'    "{link}",\n')
            f.write("]\n")
        
        print(f"📄 Linkler '{dosya_adi}' dosyasına kaydedildi.")
        browser.close()

if __name__ == "__main__":
    mismar_ajan()