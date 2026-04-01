import streamlit as st
import sqlite3
import pandas as pd
import re

st.set_page_config(page_title="Market Gelsin", layout="wide", page_icon="🛒")

# --- NORMALIZE (EŞLEŞTİRME) ---
def normalize(text):
    text = text.lower()
    text = re.sub(r"\d+\s*(ml|lt|l|gr|g|kg)", "", text)
    text = re.sub(r"[^a-zçğıöşü\s]", "", text)
    return text.strip()

# --- VERİ ---
def veri_getir():
    conn = sqlite3.connect("marketler.db")
    df = pd.read_sql_query("SELECT * FROM urunler", conn)
    conn.close()
    df["norm"] = df["urun_adi"].apply(normalize)
    return df

df = veri_getir()

st.title("🛒 Market Gelsin - Akıllı Karşılaştırma")

# --- MOBİL UYUMLU ---
st.markdown("""
<style>
@media (max-width:768px){
    h1 {font-size:22px;}
    .block-container {padding:10px;}
}
</style>
""", unsafe_allow_html=True)

# --- ARAMA ---
urun_ara = st.text_input("🔍 Ürün Ara (örn: süt, peynir, yağ)")
df2 = df.copy()

if urun_ara:
    df2 = df2[df2["urun_adi"].str.contains(urun_ara, case=False, na=False)]

urun_listesi = df2["norm"].unique().tolist()
sec_norm = st.selectbox("🧾 Karşılaştırılacak ürün:", [""] + urun_listesi)

if sec_norm:
    sec_df = df[df["norm"] == sec_norm]
    sec_df = sec_df.sort_values("fiyat")

    st.subheader("📊 Market Karşılaştırması")

    en_ucuz = sec_df["fiyat"].min()

    cols = st.columns(len(sec_df))
    for i,row in enumerate(sec_df.itertuples()):
        with cols[i]:
            with st.container(border=True):
                st.image(row.gorsel if row.gorsel else "https://cdn-icons-png.flaticon.com/512/1170/1170576.png", use_container_width=True)
                st.markdown(f"**{row.market}**")
                if row.fiyat == en_ucuz:
                    st.success(f"{row.fiyat} TL (EN UCUZ)")
                else:
                    st.markdown(f"### {row.fiyat} TL")

    # --- GRAFİK ---
    st.subheader("📈 Fiyat Grafiği")
    chart_df = sec_df[["market","fiyat"]]
    st.bar_chart(chart_df.set_index("market"))

    # --- ALARM ---
    st.subheader("⏰ Fiyat Alarmı")
    hedef = st.number_input("Fiyat şu seviyeye düşerse haber ver:", min_value=0.0)

    if st.button("Alarm Kur"):
        if en_ucuz <= hedef:
            st.success("🔔 Fiyat hedefin altına düştü!")
        else:
            st.warning("Henüz düşmedi, takip ediliyor.")

# --- TABLO ---
st.divider()
st.subheader("📦 Tüm Ürünler")
st.dataframe(df[["urun_adi","market","fiyat","kategori"]], use_container_width=True)
