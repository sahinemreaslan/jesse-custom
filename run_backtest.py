"""
Jesse Gerçek Backtest
SimpleMAStrategy ile gerçek Binance verileri üzerinde backtest yapar
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

from jesse.research import backtest
from jesse.enums import timeframes
import routes as my_routes

print("="*70)
print("JESSE GERÇEK BACKTEST")
print("="*70)
print(f"\nStrateji: SimpleMAStrategy")
print(f"Borsa: Binance Futures")
print(f"Sembol: BTC-USDT")
print(f"Timeframe: 1 saat")
print(f"Tarih: 2023-01-01 - 2024-12-31")
print("\n" + "="*70)

# Backtest çalıştır
try:
    result = backtest(
        routes=my_routes.routes,
        start_date='2023-01-01',
        finish_date='2024-12-31',
    )

    print("\n" + "="*70)
    print("BACKTEST SONUÇLARI")
    print("="*70)

    if result and 'metrics' in result:
        metrics = result['metrics']

        print(f"\n💰 FİNANSAL PERFORMANS:")
        print(f"   Başlangıç Sermaye: ${result.get('starting_balance', 10000):.2f}")
        print(f"   Bitiş Sermaye: ${result.get('finishing_balance', 0):.2f}")
        print(f"   Toplam Net Kar: ${metrics.get('net_profit', 0):.2f}")
        print(f"   Toplam Net Kar %: {metrics.get('net_profit_percentage', 0):.2f}%")

        print(f"\n📊 İŞLEM İSTATİSTİKLERİ:")
        print(f"   Toplam İşlem: {metrics.get('total_trades', 0)}")
        print(f"   Kazanan İşlem: {metrics.get('total_winning_trades', 0)}")
        print(f"   Kaybeden İşlem: {metrics.get('total_losing_trades', 0)}")
        print(f"   Kazanma Oranı: {metrics.get('win_rate', 0):.2f}%")

        print(f"\n📈 PERFORMANS METRİKLERİ:")
        print(f"   Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"   Maksimum Drawdown: {metrics.get('max_drawdown', 0):.2f}%")
        print(f"   Ortalama Kazanan İşlem: ${metrics.get('average_win', 0):.2f}")
        print(f"   Ortalama Kaybeden İşlem: ${metrics.get('average_loss', 0):.2f}")

        if metrics.get('total_trades', 0) > 0:
            print(f"\n🎯 RİSK/ÖDÜL:")
            print(f"   Risk-Reward Ratio: {metrics.get('ratio_avg_win_loss', 0):.2f}")

    else:
        print("\n⚠️  Backtest sonucu alınamadı!")
        if result:
            print(f"Result: {result}")

    print("\n" + "="*70)

except Exception as e:
    print(f"\n❌ Backtest hatası: {e}")
    import traceback
    traceback.print_exc()
