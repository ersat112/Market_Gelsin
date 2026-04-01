import requests, os, re, sqlite3, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tqdm import tqdm

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0"
}

DB = "marketler.db"
IMG_DIR = "images"

os.makedirs(IMG_DIR, exist_ok=True)

######################################
# DB
######################################

def db_connect():
    return sqlite3.connect(DB)

def db_setup():
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS urunler(
        sku TEXT PRIMARY KEY,
        market TEXT,
        kategori TEXT,
        ad TEXT,
        fiyat REAL,
        resim TEXT
    )
    """)
    conn.commit()
    conn.close()

def kaydet(market, kategori, ad, fiyat, resim):
    sku = str(abs(hash(market+ad+kategori)))[:12]
    conn = db_connect()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO urunler VALUES(?,?,?,?,?,?)",
              (sku, market, kategori, ad, fiyat, resim))
    conn.commit()
    conn.close()

######################################
# ORTAK
######################################

def temiz_fiyat(txt):
    return float(re.sub(r"[^\d,]", "", txt).replace(",", "."))

def resim_indir(url, market):
    if not url:
        return ""
    ext = url.split("?")[0].split(".")[-1]
    name = str(abs(hash(url)))
    path = f"{IMG_DIR}/{market}"
    os.makedirs(path, exist_ok=True)
    full = f"{path}/{name}.{ext}"
    if os.path.exists(full):
        return full
    r = requests.get(url, headers=HEADERS, timeout=20)
    with open(full, "wb") as f:
        f.write(r.content)
    return full

######################################
# MIGROS
######################################

def migros_kategoriler():
    url = "https://www.migros.com.tr"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "lxml")
    return [urljoin(url,a["href"]) for a in soup.select("a[href*='-c-']")]

def migros_urunler(kat_url):
    page = 1
    while True:
        url = f"{kat_url}?page={page}"
        r = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(r.text, "lxml")
        cards = soup.select(".product-card")
        if not cards:
            break
        for c in cards:
            try:
                ad = c.select_one(".product-name").text.strip()
                fiyat = temiz_fiyat(c.select_one(".price").text)
                img = c.select_one("img")["src"]
                yield ad,fiyat,img
            except:
                continue
        page += 1

######################################
# ŞOK
######################################

def sok_kategoriler():
    url = "https://www.sokmarket.com.tr"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "lxml")
    return [urljoin(url,a["href"]) for a in soup.select("a[href*='-c-']")]

def sok_urunler(kat_url):
    r = requests.get(kat_url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "lxml")
    cards = soup.select("div.product-item")
    for c in cards:
        try:
            ad = c.select_one("h3").text.strip()
            fiyat = temiz_fiyat(c.select_one(".price").text)
            img = c.select_one("img")["src"]
            yield ad,fiyat,img
        except:
            continue

######################################
# MİSMAR
######################################

def mismar_kategoriler():
    url = "https://www.mismarsanalmarket.com"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "lxml")
    return [urljoin(url,a["href"]) for a in soup.select(".category-list a")]

def mismar_urunler(kat_url):
    r = requests.get(kat_url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "lxml")
    cards = soup.select(".product-item")
    for c in cards:
        try:
            ad = c.select_one(".product-name").text.strip()
            fiyat = temiz_fiyat(c.select_one(".price").text)
            img = c.select_one("img")["src"]
            yield ad,fiyat,img
        except:
            continue

######################################
# ANA
######################################

def calistir():
    db_setup()

    print("🟠 Migros")
    for kat in migros_kategoriler():
        kat_adi = kat.split("/")[-1]
        for ad,fiyat,img in migros_urunler(kat):
            resim = resim_indir(img,"migros")
            kaydet("Migros",kat_adi,ad,fiyat,resim)

    print("🟡 Şok")
    for kat in sok_kategoriler():
        kat_adi = kat.split("/")[-1]
        for ad,fiyat,img in sok_urunler(kat):
            resim = resim_indir(img,"sok")
            kaydet("Sok",kat_adi,ad,fiyat,resim)

    print("🟢 Mismar")
    for kat in mismar_kategoriler():
        kat_adi = kat.split("/")[-1]
        for ad,fiyat,img in mismar_urunler(kat):
            resim = resim_indir(img,"mismar")
            kaydet("Mismar",kat_adi,ad,fiyat,resim)

    print("✅ TAMAMLANDI")

if __name__ == "__main__":
    calistir()
