import streamlit as st
import sqlite3
import pandas as pd
import os

st.set_page_config(page_title="Market Gelsin", layout="wide", page_icon="🛒")

DB_NAME = "marketler.db"

def veri_getir():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM urunler", conn)
    conn.close()
    return df

st.title("🛒 Market Gelsin - Fiyat Karşılaştırma")

try:
    df = veri_getir()

    # İstatistikler
    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Ürün", len(df))
    col2.metric("Sok Ürünleri", len(df[df['market'] == "Sok"]))
    col3.metric("Diğer Marketler", len(df[df['market'] != "Sok"]))

    st.divider()

    # Sidebar
    st.sidebar.header("🔍 Filtre")

    arama = st.sidebar.text_input("Ürün Ara")

    kategoriler = ["Tümü"] + sorted(df["kategori"].dropna().unique().tolist())
    secilen_kategori = st.sidebar.selectbox("Kategori", kategoriler)

    marketler = ["Tümü"] + sorted(df["market"].dropna().unique().tolist())
    secilen_market = st.sidebar.selectbox("Market", marketler)

    df_filtered = df.copy()

    if arama:
        df_filtered = df_filtered[df_filtered["ad"].str.contains(arama, case=False, na=False)]

    if secilen_kategori != "Tümü":
        df_filtered = df_filtered[df_filtered["kategori"] == secilen_kategori]

    if secilen_market != "Tümü":
        df_filtered = df_filtered[df_filtered["market"] == secilen_market]

    st.subheader(f"Sonuçlar ({len(df_filtered)} ürün)")

    cols = st.columns(4)

    for i, row in df_filtered.iterrows():
        with cols[i % 4]:
            with st.container(border=True):

                if row["resim"] and os.path.exists(row["resim"]):
                    st.image(row["resim"], use_container_width=True)
                else:
                    st.image(
                        "https://cdn-icons-png.flaticon.com/512/1170/1170576.png",
                        width=100
                    )

                st.markdown(f"**{row['ad']}**")
                st.markdown(f"### {row['fiyat']} TL")
                st.caption(f"{row['market']} | {row['kategori']}")

except Exception as e:
    st.error("Veritabanı okunamadı")
    st.error(e)
