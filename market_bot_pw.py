from playwright.sync_api import sync_playwright
import time

def scroll_to_bottom(page, max_scroll=50):
    last_count = 0

    for i in range(max_scroll):
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1200)

        cards = page.query_selector_all("sm-product-card")
        count = len(cards)

        if count == last_count:
            break  # yeni ürün gelmiyorsa dur
        last_count = count

    return last_count


def migros(page):
    print("🟠 Migros")
    url = "https://www.migros.com.tr"
    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    try:
        page.wait_for_selector("sm-product-card", timeout=30000)
        total = scroll_to_bottom(page, 80)
        print(f"   ✔ Migros ürün bulundu: {total}")
    except:
        print("   ❌ Migros ürün bulunamadı")


def sok(page):
    print("🟡 Şok")
    url = "https://www.sokmarket.com.tr"
    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    try:
        page.wait_for_selector("div.product-item", timeout=30000)
        scroll_count = 0
        last = 0

        for _ in range(60):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1200)

            products = page.query_selector_all("div.product-item")
            count = len(products)

            if count == last:
                break
            last = count

        print(f"   ✔ Sok ürün bulundu: {last}")
    except:
        print("   ❌ Sok ürün bulunamadı")


def mismar(page):
    print("🟢 Mismar")
    url = "https://www.mismarmarket.com.tr"
    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    try:
        page.wait_for_selector(".product-item", timeout=30000)
        scroll_count = 0
        last = 0

        for _ in range(60):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1200)

            products = page.query_selector_all(".product-item")
            count = len(products)

            if count == last:
                break
            last = count

        print(f"   ✔ Mismar ürün bulundu: {last}")
    except:
        print("   ❌ Mismar ürün bulunamadı")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Arka planda çalışır
        page = browser.new_page()

        migros(page)
        sok(page)
        mismar(page)

        print("✅ TAMAMLANDI")
        browser.close()


if __name__ == "__main__":
    main()
