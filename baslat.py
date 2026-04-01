import os
import time

# --- MODÜLLERİ İÇERİ ALIYORUZ ---
# Eğer dosya isimlerin farklıysa buradan düzeltebilirsin
try:
    from mismar_turbo import TurboMismar  # Mismar (Hızlı + Resimli)
    from sok_migros_garanti import GarantiBot  # Şok & Migros (Garantili + Uzun Liste)
except ImportError as e:
    print(f"🚨 HATA: Dosyalar bulunamadı! {e}")
    print("Lütfen 'mismar_turbo.py' ve 'sok_migros_garanti.py' dosyalarının klasörde olduğundan emin ol.")
    exit()

def temizlik_yap():
    db_file = "market_verisi.db"
    if os.path.exists(db_file):
        print("🗑️  Eski veritabanı siliniyor (Temiz Kurulum)...")
        try:
            os.remove(db_file)
            time.sleep(1)
            print("✨ Veritabanı tertemiz, sıfırdan başlıyoruz!")
        except Exception as e:
            print(f"⚠️ Dosya silinemedi (Açık olabilir): {e}")
    else:
        print("✨ Veritabanı zaten yok, sıfırdan başlıyoruz.")

def operasyonu_baslat():
    print("\n==========================================")
    print("🚀 MARKET GELSİN: BÜYÜK VERİ OPERASYONU")
    print("==========================================")
    
    # 1. ADIM: TEMİZLİK
    temizlik_yap()
    
    # 2. ADIM: MİSMAR (TURBO MOD)
    print("\n" + "="*40)
    print("🟢 AŞAMA 1: Mismar Sanal Market (Turbo Mod)")
    print("="*40)
    try:
        # Mismar motorunu çalıştır
        TurboMismar().motoru_calistir()
    except Exception as e:
        print(f"⚠️ Mismar Modülünde Hata: {e}")
    
    # 3. ADIM: ŞOK VE MİGROS (GARANTİ MOD)
    print("\n" + "="*40)
    print("🟠 AŞAMA 2: Şok ve Migros (Garantili Mod)")
    print("   (Tarayıcı açılacak, lütfen müdahale etme...)")
    print("="*40)
    try:
        # Şok ve Migros motorunu çalıştır
        GarantiBot().baslat()
    except Exception as e:
        print(f"⚠️ Garanti Bot Modülünde Hata: {e}")
    
    print("\n==========================================")
    print("🏁 OPERASYON BAŞARIYLA TAMAMLANDI!")
    print("🎉 Şimdi 'streamlit run app.py' yazarak uygulamayı açabilirsin.")
    print("==========================================")

if __name__ == "__main__":
    operasyonu_baslat()