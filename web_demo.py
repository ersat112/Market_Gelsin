import streamlit as st
import sqlite3
import pandas as pd
import os

# Sayfa ayarları
st.set_page_config(page_title="Konya Market Avcısı", layout="wide", page_icon="🦁")

# --- CSS: TASARIM VE RENKLER ---
st.markdown("""
<style>
    .market-badge {
        padding: 5px 10px;
        border-radius: 5px;
        color: white;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 5px;
        font-size: 0.9em;
    }
    .migros { background-color: #ff9800; }
    .sok { background-color: #fdd835; color: black !important; }
    .mismar { background-color: #4caf50; }
    .other { background-color: #9e9e9e; }
    
    /* Kart Efekti */
    div[data-testid="column"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 10px;
        background-color: white;
        transition: 0.3s;
    }
    div[data-testid="column"]:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# --- VERİ YÜKLEME (ÇOKLU VERİTABANI DESTEĞİ) ---
@st.cache_data
def veri_yukle():
    tum_veriler = []
    
    # Okunacak veritabanı dosyaları listesi
    db_dosyalari = [
        "konya_market_verisi.db", 
        "Migros.db", 
        "Sok.db", 
        "Mismar.db"
    ]
    
    for db_yolu in db_dosyalari:
        if os.path.exists(db_yolu):
            try:
                conn = sqlite3.connect(db_yolu)
                # Tablo adını kontrol et (Genelde 'urunler' tablosu)
                query = "SELECT * FROM urunler"
                df = pd.read_sql_query(query, conn)
                conn.close()
                
                # Eğer 'market' sütunu yoksa, dosya isminden market adı ver
                if 'market' not in df.columns:
                    if "Migros" in db_yolu: df['market'] = "Migros"
                    elif "Sok" in db_yolu: df['market'] = "Şok"
                    elif "Mismar" in db_yolu: df['market'] = "Mismar"
                    else: df['market'] = "Diğer"
                
                tum_veriler.append(df)
            except Exception as e:
                # Hata olursa (örneğin boş db) pas geç
                continue
                
    if tum_veriler:
        # Tüm tabloları alt alta birleştir
        ana_tablo = pd.concat(tum_veriler, ignore_index=True)
        
        # Temizlik: Fiyatı sayıya çevir, hatalıları sil
        ana_tablo['fiyat'] = pd.to_numeric(ana_tablo['fiyat'], errors='coerce')
        ana_tablo = ana_tablo.dropna(subset=['fiyat']) # Fiyatı olmayanları sil
        
        # Tekrar eden ürünleri temizle (Aynı SKU varsa sonuncuyu tut)
        if 'sku' in ana_tablo.columns:
            ana_tablo = ana_tablo.drop_duplicates(subset=['sku'], keep='last')
            
        return ana_tablo
        
    return pd.DataFrame()

# Veriyi Yükle
df = veri_yukle()

# Veri Kontrolü
if df.empty:
    st.error("⚠️ Hiçbir veritabanı dosyasında veri bulunamadı! Lütfen önce 'python market.py' ile tarama yapın.")
    st.stop()

# Sepet Hafızası
if 'sepet' not in st.session_state:
    st.session_state.sepet = []

# --- SOL MENÜ ---
with st.sidebar:
    st.title("⚙️ Filtreler")
    
    # Market Seçimi
    mevcut_marketler = sorted(list(df['market'].unique()))
    secili_marketler = st.multiselect(
        "Market Seçimi",
        mevcut_marketler,
        default=mevcut_marketler
    )
    
    st.markdown("---")
    
    # Sepet
    st.header(f"🛒 Sepetim ({len(st.session_state.sepet)})")
    if st.session_state.sepet:
        toplam = 0
        for item in st.session_state.sepet:
            c1, c2 = st.columns([3, 1])
            c1.caption(f"{item['market']} - {item['ad'][:12]}..")
            c2.caption(f"{item['fiyat']}₺")
            toplam += item['fiyat']
        
        st.markdown(f"### Toplam: :green[{toplam:.2f} TL]")
        if st.button("🗑️ Temizle"):
            st.session_state.sepet = []
            st.rerun()
    else:
        st.info("Sepet boş.")

# --- ANA EKRAN ---
st.title("🦁 Konya Market Avcısı")
st.markdown(f"Toplam **{len(df)}** ürün veritabanında mevcut.")

# Arama ve Kategori
c1, c2 = st.columns([3, 1])
arama = c1.text_input("🔍 Ürün Ara", placeholder="Örn: Salça, Süt, Çay, Yumurta")
kategoriler = ["Tümü"] + sorted([str(k) for k in df['kategori'].unique() if k])
secilen_kategori = c2.selectbox("Kategori", kategoriler)

# --- FİLTRELEME ---
filtrelenmis = df.copy()

# 1. Market Filtresi
filtrelenmis = filtrelenmis[filtrelenmis['market'].isin(secili_marketler)]

# 2. Arama
if arama:
    filtrelenmis = filtrelenmis[filtrelenmis['urun_adi'].str.contains(arama, case=False)]

# 3. Kategori
if secilen_kategori != "Tümü":
    filtrelenmis = filtrelenmis[filtrelenmis['kategori'] == secilen_kategori]

# 4. Sıralama (En Ucuzdan Pahalıya)
filtrelenmis = filtrelenmis.sort_values(by='fiyat', ascending=True)

# --- LİSTELEME ---
if len(filtrelenmis) == 0:
    st.warning("😔 Ürün bulunamadı.")
    if not arama:
        st.markdown("### 🔥 Hızlı Aramalar")
        cols = st.columns(4)
        if cols[0].button("🥛 Süt"): st.rerun()
        if cols[1].button("🥫 Salça"): st.rerun()
        if cols[2].button("🧼 Deterjan"): st.rerun()
        if cols[3].button("🍗 Tavuk"): st.rerun()
else:
    st.success(f"**{len(filtrelenmis)}** sonuç bulundu.")
    
    cols = st.columns(4)
    for index, row in filtrelenmis.iterrows():
        col = cols[index % 4]
        with col:
            # Market Logosu
            m = str(row['market']).lower()
            if "migros" in m: 
                stil = "migros"; ikon = "🟠"
            elif "sok" in m or "şok" in m: 
                stil = "sok"; ikon = "🟡"
            elif "mismar" in m: 
                stil = "mismar"; ikon = "🟢"
            else: 
                stil = "other"; ikon = "🏢"
            
            st.markdown(f'<div class="market-badge {stil}">{ikon} {row["market"]}</div>', unsafe_allow_html=True)
            
            # Resim
            img = row['gorsel']
            if img and os.path.exists(str(img)):
                st.image(str(img), use_container_width=True)
            elif img and str(img).startswith("http"):
                st.image(str(img), use_container_width=True)
            else:
                st.image("https://via.placeholder.com/150?text=Resim+Yok", use_container_width=True)
            
            st.markdown(f"**{row['urun_adi']}**")
            st.markdown(f"#### {row['fiyat']} TL")
            
            if st.button("Sepete Ekle ➕", key=f"add_{index}"):
                st.session_state.sepet.append({
                    "ad": row['urun_adi'],
                    "fiyat": row['fiyat'],
                    "market": row['market']
                })
                st.rerun()