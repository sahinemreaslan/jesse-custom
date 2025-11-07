"""
HIZLI PAPER TRADING TEST - Otomatik Başlat
═══════════════════════════════════════════════════════════
Parametreler hazır, direkt başlatır
Input gerektirmez

Kullanım:
  python quick_paper_test.py

Ctrl+C ile durdurun
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

from paper_trading_engine import PaperTradingEngine

# Parametreler
SYMBOL = 'BTC/USDT'
CAPITAL = 10000
CHECK_INTERVAL = 300  # 5 dakika (300 saniye)

print("\n" + "="*80)
print("⚡ HIZLI PAPER TRADING TEST")
print("="*80)
print(f"""
Parametreler:
  Symbol: {SYMBOL}
  Sermaye: ${CAPITAL:,.2f}
  Kontrol Aralığı: {CHECK_INTERVAL//60} dakika

⚠️  PARA RİSKİ YOK - SADECE TEST!

Başlatılıyor...
""")
print("="*80)

# Engine oluştur
engine = PaperTradingEngine(symbol=SYMBOL, initial_capital=CAPITAL)

# Çalıştır
try:
    engine.run(check_interval=CHECK_INTERVAL)
except KeyboardInterrupt:
    print("\n\n⚠️  Durduruldu!")
    engine.print_final_report()
