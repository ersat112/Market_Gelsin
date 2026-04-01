from database import MarketDB

db = MarketDB()
# Örnek barkod ve ürünler
db.veri_ekle("8690504000012", "Dost Süt 1L", "BİM", 24.50)
db.veri_ekle("8690504000012", "Dost Süt 1L", "A101", 26.00)
db.veri_ekle("8680001234567", "Vera Yağ 5L", "A101", 195.00)

print("Test verileri başarıyla eklendi! Şimdi tarayıcıyı yenile.")
