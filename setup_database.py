"""
Jesse veritabanı tablolarını oluştur
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

from jesse.services.db import database
from jesse.models import Candle, Trade, Order, DailyBalance

print("="*70)
print("JESSE VERİTABANI KURULUMU")
print("="*70)

# Veritabanı bağlantısı
if database.is_closed():
    database.connect()

print("\n1. Tabloları oluşturuyor...")

# Tabloları oluştur
for model in [Candle, Trade, Order, DailyBalance]:
    model.create_table(fail_silently=True)

print("✅ Tablolar oluşturuldu!")

# Unique index oluştur
print("\n2. Index'leri oluşturuyor...")

try:
    # Candle tablosu için unique index
    database.execute_sql('''
        CREATE UNIQUE INDEX IF NOT EXISTS candle_unique
        ON candle (exchange, symbol, timestamp);
    ''')
    print("✅ Candle unique index oluşturuldu!")
except Exception as e:
    print(f"⚠️  Index zaten var veya hata: {e}")

print("\n✅ Veritabanı kurulumu tamamlandı!")
print("="*70)

# Bağlantıyı kapat
if not database.is_closed():
    database.close()
