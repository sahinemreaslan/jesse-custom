"""
Jesse Backtest Runner
Gerçek piyasa verileri ile backtest yapar
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

from jesse import research
from jesse.config import config
from jesse.enums import timeframes
from jesse.routes import router
from datetime import datetime
import routes as my_routes

# Import config
import config as my_config

# Set routes
router.set_routes(my_routes.routes)

print("="*70)
print("JESSE BACKTEST - Simple MA Strategy")
print("="*70)
print("\nBacktest başlatılıyor...")
print(f"Strateji: SimpleMAStrategy")
print(f"Borsa: Binance Futures")
print(f"Sembol: BTC-USDT")
print(f"Zaman dilimi: 1 saat")
print("\n" + "="*70)

# Run backtest
# Not: Gerçek veriler gerekli, şimdilik basit bir örnek yapalım
print("\n⚠️  Gerçek backtest için önce veri indirmemiz gerekiyor!")
print("\nVeri indirme adımları:")
print("1. jesse import-candles 'Binance Futures' 'BTC-USDT' 2023-01-01")
print("2. Bu script'i tekrar çalıştır")
print("\n" + "="*70)
