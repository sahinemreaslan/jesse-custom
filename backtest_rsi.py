"""
RSI Mean Reversion Strategy Backtest
Gerçek Binance verileri ile RSI stratejisini test eder
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
from datetime import datetime

print("="*70)
print("RSI MEAN REVERSION STRATEGY BACKTEST")
print("="*70)
print("\nStrateji Kuralları:")
print("  • Giriş: RSI < 30 (Oversold - aşırı satım)")
print("  • Çıkış: RSI > 70 (Overbought) veya TP/SL")
print("  • Take Profit: +%15")
print("  • Stop Loss: -%7")
print("  • Pozisyon Büyüklüğü: Bakiyenin %10'u")
print("="*70)

# Veritabanından verileri çek
conn = psycopg2.connect(
    host='127.0.0.1',
    database='jesse_db',
    user='voidstring',
    password=''
)

cursor = conn.cursor()
cursor.execute('''
    SELECT timestamp, open, high, low, close, volume
    FROM candle
    WHERE exchange = 'Binance Futures'
      AND symbol = 'BTC-USDT'
      AND timeframe = '1h'
      AND timestamp >= 1672531200000  -- 2023-01-01
      AND timestamp <= 1704067199000  -- 2023-12-31
    ORDER BY timestamp ASC;
''')

data = cursor.fetchall()
cursor.close()
conn.close()

print(f"\n✅ {len(data)} mum yüklendi")
print(f"   Başlangıç: {datetime.fromtimestamp(data[0][0]/1000).strftime('%Y-%m-%d')}")
print(f"   Bitiş: {datetime.fromtimestamp(data[-1][0]/1000).strftime('%Y-%m-%d')}")

# DataFrame oluştur
df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

# RSI hesapla
def calculate_rsi(prices, period=14):
    """RSI hesaplama"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

df['rsi'] = calculate_rsi(df['close'], 14)

# Sinyaller
df['signal'] = 0
df.loc[df['rsi'] < 30, 'signal'] = 1  # Long sinyali (oversold)

# Backtest simülasyonu
balance = 10000
position = None
trades = []

print("\n⏳ Backtest çalıştırılıyor...")

for i in range(50, len(df)):
    row = df.iloc[i]
    price = row['close']
    rsi = row['rsi']

    # Sinyal kontrolü
    if row['signal'] == 1 and position is None and not pd.isna(rsi):
        # Long giriş (RSI < 30)
        qty = (balance * 0.10) / price  # %10 pozisyon
        position = {
            'entry_price': price,
            'qty': qty,
            'entry_time': row['timestamp'],
            'tp': price * 1.15,  # %15 TP
            'sl': price * 0.93,  # %7 SL
            'entry_rsi': rsi
        }

    elif position is not None:
        # Çıkış kontrolü

        # RSI overbought (70 üstü) - pozisyonu kapat
        if rsi > 70 and not pd.isna(rsi):
            profit = (price - position['entry_price']) * position['qty']
            balance += profit
            trades.append({
                'profit': profit,
                'type': 'RSI>70',
                'entry': position['entry_price'],
                'exit': price,
                'entry_rsi': position['entry_rsi'],
                'exit_rsi': rsi
            })
            position = None

        # Take profit
        elif price >= position['tp']:
            profit = (price - position['entry_price']) * position['qty']
            balance += profit
            trades.append({
                'profit': profit,
                'type': 'TP',
                'entry': position['entry_price'],
                'exit': price,
                'entry_rsi': position['entry_rsi'],
                'exit_rsi': rsi
            })
            position = None

        # Stop loss
        elif price <= position['sl']:
            profit = (price - position['entry_price']) * position['qty']
            balance += profit
            trades.append({
                'profit': profit,
                'type': 'SL',
                'entry': position['entry_price'],
                'exit': price,
                'entry_rsi': position['entry_rsi'],
                'exit_rsi': rsi
            })
            position = None

# Sonuçlar
print("\n" + "="*70)
print("BACKTEST SONUÇLARI")
print("="*70)

if trades:
    total_profit = sum(t['profit'] for t in trades)
    winning_trades = [t for t in trades if t['profit'] > 0]
    losing_trades = [t for t in trades if t['profit'] < 0]

    print(f"\n💰 FİNANSAL PERFORMANS:")
    print(f"   Başlangıç Sermaye: $10,000.00")
    print(f"   Bitiş Sermaye: ${balance:.2f}")
    print(f"   Toplam Net Kar: ${total_profit:.2f}")
    print(f"   Getiri: {(total_profit / 10000 * 100):.2f}%")

    print(f"\n📊 İŞLEM İSTATİSTİKLERİ:")
    print(f"   Toplam İşlem: {len(trades)}")
    print(f"   Kazanan İşlem: {len(winning_trades)}")
    print(f"   Kaybeden İşlem: {len(losing_trades)}")

    if len(trades) > 0:
        win_rate = len(winning_trades) / len(trades) * 100
        print(f"   Kazanma Oranı: {win_rate:.2f}%")

    # Çıkış tipi istatistikleri
    tp_count = len([t for t in trades if t['type'] == 'TP'])
    sl_count = len([t for t in trades if t['type'] == 'SL'])
    rsi_count = len([t for t in trades if t['type'] == 'RSI>70'])

    print(f"\n📈 ÇIKIŞ TİPLERİ:")
    print(f"   Take Profit (%15): {tp_count}")
    print(f"   Stop Loss (-%7): {sl_count}")
    print(f"   RSI Overbought (>70): {rsi_count}")

    if winning_trades:
        avg_win = sum(t['profit'] for t in winning_trades) / len(winning_trades)
        print(f"\n💡 PERFORMANS METRİKLERİ:")
        print(f"   Ortalama Kazanç: ${avg_win:.2f}")

    if losing_trades:
        avg_loss = sum(t['profit'] for t in losing_trades) / len(losing_trades)
        print(f"   Ortalama Zarar: ${avg_loss:.2f}")

    print(f"\n🎯 İLK 10 İŞLEM:")
    for i, trade in enumerate(trades[:10], 1):
        print(f"   {i}. {trade['type']:8} - Giriş: ${trade['entry']:.2f} (RSI:{trade['entry_rsi']:.1f}), "
              f"Çıkış: ${trade['exit']:.2f} (RSI:{trade['exit_rsi']:.1f}), P/L: ${trade['profit']:.2f}")

    # Karşılaştırma
    print(f"\n📊 KARŞILAŞTIRMA:")
    print(f"   RSI Stratejisi: {(total_profit / 10000 * 100):.2f}%")
    print(f"   (SimpleMA'dan daha {'iyi' if total_profit > 507.38 else 'kötü'})")
else:
    print("\n⚠️  Hiç işlem gerçekleşmedi!")

print("\n" + "="*70)
print("✅ Backtest tamamlandı!")
print("="*70)
