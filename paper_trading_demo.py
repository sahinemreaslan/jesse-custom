"""
PAPER TRADING DEMO - Hızlı Test Modu
═══════════════════════════════════════════════════════════
Demo amaçlı - Her 5 dakikada bir kontrol eder
Gerçek kullanım için: paper_trading_engine.py (1 saatte bir)

Kullanım:
  python paper_trading_demo.py

Not: CTRL+C ile durdurun
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

from paper_trading_engine import PaperTradingEngine


def main():
    """Demo modu - Her 5 dakikada kontrol"""

    print("\n" + "="*80)
    print("PAPER TRADING DEMO - HIZLI TEST MODU")
    print("="*80)
    print("""
⚡ DEMO MODU: Her 5 DAKİKADA bir kontrol edilir

⚠️  ÖNEMLİ:
   - Gerçek para riski YOK!
   - Sadece simülasyon ve test amaçlı
   - Ctrl+C ile durdurun

💡 Gerçek kullanım için: paper_trading_engine.py (1 saatte bir)
    """)

    # Parametreler
    symbol = input("Symbol (varsayılan: BTC/USDT): ").strip() or "BTC/USDT"
    capital = input("Başlangıç sermayesi (varsayılan: 10000): ").strip() or "10000"
    capital = float(capital)

    confirm = input(f"\n✅ {symbol} için ${capital:,.2f} ile demo başlatılsın mı? (y/n): ").lower()

    if confirm != 'y':
        print("❌ İptal edildi.")
        return

    # Engine başlat
    engine = PaperTradingEngine(symbol=symbol, initial_capital=capital)

    print(f"\n{'='*80}")
    print(f"⚡ DEMO MODU: Her 5 dakikada kontrol")
    print(f"{'='*80}\n")

    # Çalıştır (her 5 dakika = 300 saniye)
    engine.run(check_interval=300)


if __name__ == '__main__':
    main()
