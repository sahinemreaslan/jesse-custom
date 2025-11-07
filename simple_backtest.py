"""
Manuel Backtest - Jesse verileri ile SimpleMAStrategy
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
from strategies.SimpleMAStrategy import SimpleMAStrategy
from datetime import datetime

print("="*70)
print("MANUEL BACKTEST - SimpleMAStrategy")
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

# Basit backtest mantığı
def calculate_ema(prices, period):
    """EMA hesapla"""
    return prices.ewm(span=period, adjust=False).mean()

# EMA'ları hesapla
df['ema8'] = calculate_ema(df['close'], 8)
df['ema21'] = calculate_ema(df['close'], 21)

# Sinyaller
df['signal'] = 0
df.loc[df['ema8'] > df['ema21'], 'signal'] = 1  # Long sinyali

# Backtest simülasyonu
balance = 10000
position = None
trades = []

for i in range(50, len(df)):  # İlk 50 mumu EMA hesaplama için atla
    row = df.iloc[i]
    price = row['close']

    # Sinyal kontrolü
    if row['signal'] == 1 and position is None:
        # Long giriş
        qty = (balance * 0.05) / price
        position = {
            'entry_price': price,
            'qty': qty,
            'entry_time': row['timestamp'],
            'tp': price * 1.10,
            'sl': price * 0.95
        }

    elif position is not None:
        # Çıkış kontrolü
        if price >= position['tp']:
            # Take profit
            profit = (price - position['entry_price']) * position['qty']
            balance += profit
            trades.append({
                'profit': profit,
                'type': 'TP',
                'entry': position['entry_price'],
                'exit': price
            })
            position = None

        elif price <= position['sl']:
            # Stop loss
            profit = (price - position['entry_price']) * position['qty']
            balance += profit
            trades.append({
                'profit': profit,
                'type': 'SL',
                'entry': position['entry_price'],
                'exit': price
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

    if winning_trades:
        avg_win = sum(t['profit'] for t in winning_trades) / len(winning_trades)
        print(f"\n📈 PERFORMANS METRİKLERİ:")
        print(f"   Ortalama Kazanç: ${avg_win:.2f}")

    if losing_trades:
        avg_loss = sum(t['profit'] for t in losing_trades) / len(losing_trades)
        print(f"   Ortalama Zarar: ${avg_loss:.2f}")

    print(f"\n💡 İLK 10 İŞLEM:")
    for i, trade in enumerate(trades[:10], 1):
        print(f"   {i}. {trade['type']} - Giriş: ${trade['entry']:.2f}, "
              f"Çıkış: ${trade['exit']:.2f}, P/L: ${trade['profit']:.2f}")
else:
    print("\n⚠️  Hiç işlem gerçekleşmedi!")

print("\n" + "="*70)
print("✅ Backtest tamamlandı!")
print("="*70)
