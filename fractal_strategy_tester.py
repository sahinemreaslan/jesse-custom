"""
Fraktal Strateji Test Motoru
Farklı fraktal kombinasyonlarını test eder ve en iyilerini bulur
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
from datetime import datetime
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
import numpy as np


def load_data():
    """Veritabanından veri yükle"""
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

    query = '''
        SELECT timestamp, open, high, low, close, volume
        FROM candle
        WHERE exchange = 'Binance Futures'
          AND symbol = 'BTC-USDT'
          AND timeframe = '1h'
          AND timestamp >= 1672531200000
          AND timestamp <= 1704067199000
        ORDER BY timestamp ASC;
    '''

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df


def backtest_fractal_strategy(df, strategy_config):
    """
    Fraktal strateji backtest motoru

    Args:
        df: OHLCV verileri
        strategy_config: Strateji konfigürasyonu
            {
                'name': str,
                'entry_patterns': list,  # Giriş yapılacak paternler
                'exit_patterns': list,   # Çıkış yapılacak paternler
                'min_strength': float,   # Minimum güç eşiği
                'position_size': float,  # Pozisyon büyüklüğü (%)
                'tp_percent': float,     # Take profit (%)
                'sl_percent': float,     # Stop loss (%)
                'weights': dict          # Patern ağırlıkları
            }
    """
    # Fraktal analiz
    df = FractalAnalyzer.analyze_series(df)

    # Ağırlıklandırma
    analyzer = MultiTimeframeFractalAnalyzer(weights=strategy_config.get('weights'))
    df = analyzer.calculate_fractal_score(df)

    # Backtest
    balance = 10000
    position = None
    trades = []

    entry_patterns = strategy_config['entry_patterns']
    exit_patterns = strategy_config.get('exit_patterns', [])
    min_strength = strategy_config['min_strength']
    position_size_pct = strategy_config['position_size']
    tp_pct = strategy_config['tp_percent']
    sl_pct = strategy_config['sl_percent']

    for i in range(50, len(df)):
        row = df.iloc[i]
        price = row['close']
        pattern = row.get('fractal_pattern')
        strength = row.get('fractal_strength', 0)

        # Giriş sinyali
        if position is None and pattern in entry_patterns and strength >= min_strength:
            qty = (balance * position_size_pct) / price
            position = {
                'entry_price': price,
                'qty': qty,
                'entry_time': row['timestamp'],
                'entry_pattern': pattern,
                'entry_strength': strength,
                'tp': price * (1 + tp_pct),
                'sl': price * (1 - sl_pct)
            }

        # Çıkış sinyali
        elif position is not None:
            exit_reason = None
            exit_price = price

            # Patern bazlı çıkış
            if pattern in exit_patterns and strength >= min_strength:
                exit_reason = f'Pattern_{pattern}'

            # TP
            elif price >= position['tp']:
                exit_reason = 'TP'

            # SL
            elif price <= position['sl']:
                exit_reason = 'SL'

            if exit_reason:
                profit = (exit_price - position['entry_price']) * position['qty']
                balance += profit

                trades.append({
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'profit': profit,
                    'entry_pattern': position['entry_pattern'],
                    'entry_strength': position['entry_strength'],
                    'exit_reason': exit_reason
                })

                position = None

    return {
        'balance': balance,
        'trades': trades,
        'strategy_name': strategy_config['name']
    }


# STRATEJİ VARYASYONLARI
strategies = [
    # 1. Pure Trend Following
    {
        'name': 'Pure Trend Following',
        'entry_patterns': ['Trending Up'],
        'exit_patterns': ['Trending Down', 'Inside Bar'],
        'min_strength': 30,
        'position_size': 0.10,
        'tp_percent': 0.15,
        'sl_percent': 0.07,
        'weights': {
            'TRENDING_UP': 3.0,
            'TRENDING_DOWN': 3.0,
            'INSIDE_BAR': 0.3,
            'OUTSIDE_BAR': 1.0
        }
    },

    # 2. Momentum Breakout
    {
        'name': 'Momentum Breakout (Outside Bar)',
        'entry_patterns': ['Outside Bar'],
        'exit_patterns': ['Inside Bar'],
        'min_strength': 40,
        'position_size': 0.15,
        'tp_percent': 0.20,
        'sl_percent': 0.08,
        'weights': {
            'OUTSIDE_BAR': 4.0,
            'TRENDING_UP': 2.0,
            'INSIDE_BAR': 0.5,
            'TRENDING_DOWN': 2.0
        }
    },

    # 3. Consolidation Breakout
    {
        'name': 'Consolidation Breakout',
        'entry_patterns': ['Trending Up'],
        'exit_patterns': ['Trending Down'],
        'min_strength': 25,
        'position_size': 0.08,
        'tp_percent': 0.12,
        'sl_percent': 0.05,
        'weights': {
            'INSIDE_BAR': 1.0,
            'OUTSIDE_BAR': 2.5,
            'TRENDING_UP': 2.5,
            'TRENDING_DOWN': 2.5
        }
    },

    # 4. Conservative Trend
    {
        'name': 'Conservative Trend',
        'entry_patterns': ['Trending Up'],
        'exit_patterns': ['Trending Down', 'Inside Bar', 'Outside Bar'],
        'min_strength': 50,
        'position_size': 0.05,
        'tp_percent': 0.10,
        'sl_percent': 0.04,
        'weights': {
            'TRENDING_UP': 2.0,
            'TRENDING_DOWN': 2.0,
            'INSIDE_BAR': 1.0,
            'OUTSIDE_BAR': 1.5
        }
    },

    # 5. Aggressive Momentum
    {
        'name': 'Aggressive Momentum',
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'exit_patterns': ['Trending Down'],
        'min_strength': 35,
        'position_size': 0.20,
        'tp_percent': 0.25,
        'sl_percent': 0.10,
        'weights': {
            'OUTSIDE_BAR': 3.5,
            'TRENDING_UP': 3.0,
            'TRENDING_DOWN': 3.0,
            'INSIDE_BAR': 0.2
        }
    },

    # 6. Balanced Multi-Pattern
    {
        'name': 'Balanced Multi-Pattern',
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'exit_patterns': ['Trending Down', 'Inside Bar'],
        'min_strength': 30,
        'position_size': 0.10,
        'tp_percent': 0.15,
        'sl_percent': 0.06,
        'weights': {
            'TRENDING_UP': 2.0,
            'TRENDING_DOWN': 2.0,
            'OUTSIDE_BAR': 2.5,
            'INSIDE_BAR': 0.5
        }
    },
]


def main():
    """Ana test fonksiyonu"""
    print("="*80)
    print("FRAKTAL STRATEJİ TEST MOTORU")
    print("="*80)
    print("\n🔍 4 Temel Fraktal Kural:")
    print("  1. Inside Bar    - Daralma / Kararsızlık")
    print("  2. Outside Bar   - Genişleme / Güçlü Momentum")
    print("  3. Trending Up   - Yükseliş Momentumu")
    print("  4. Trending Down - Düşüş Momentumu")
    print("\n" + "="*80)

    # Veri yükle
    print("\n📊 Veri yükleniyor...")
    df = load_data()
    print(f"✅ {len(df)} mum yüklendi ({datetime.fromtimestamp(df.iloc[0]['timestamp']/1000).strftime('%Y-%m-%d')} - {datetime.fromtimestamp(df.iloc[-1]['timestamp']/1000).strftime('%Y-%m-%d')})")

    # Tüm stratejileri test et
    results = []

    print(f"\n🧪 {len(strategies)} farklı strateji test ediliyor...\n")

    for i, strategy in enumerate(strategies, 1):
        print(f"⏳ [{i}/{len(strategies)}] {strategy['name']}...")

        result = backtest_fractal_strategy(df, strategy)
        results.append(result)

    # Sonuçları sırala
    results_sorted = sorted(results, key=lambda x: x['balance'], reverse=True)

    # Sonuçları göster
    print("\n" + "="*80)
    print("TEST SONUÇLARI (En İyiden En Kötüye)")
    print("="*80)

    for i, result in enumerate(results_sorted, 1):
        profit = result['balance'] - 10000
        roi = (profit / 10000) * 100
        num_trades = len(result['trades'])

        if num_trades > 0:
            winning = [t for t in result['trades'] if t['profit'] > 0]
            win_rate = (len(winning) / num_trades) * 100
            avg_profit = np.mean([t['profit'] for t in result['trades']])
        else:
            win_rate = 0
            avg_profit = 0

        print(f"\n{i}. {result['strategy_name']}")
        print(f"   💰 Getiri: {roi:+.2f}% (${profit:+.2f})")
        print(f"   📊 İşlem: {num_trades} | Kazanma: {win_rate:.1f}% | Ort P/L: ${avg_profit:.2f}")

    # En iyi 3 stratejinin detaylı analizi
    print("\n" + "="*80)
    print("🏆 EN İYİ 3 STRATEJİ - DETAYLI ANALİZ")
    print("="*80)

    for i, result in enumerate(results_sorted[:3], 1):
        trades = result['trades']

        if len(trades) == 0:
            continue

        winning = [t for t in trades if t['profit'] > 0]
        losing = [t for t in trades if t['profit'] < 0]

        print(f"\n{i}. {result['strategy_name']}")
        print(f"{'─'*80}")

        profit = result['balance'] - 10000
        roi = (profit / 10000) * 100

        print(f"   💰 FİNANSAL:")
        print(f"      Başlangıç: $10,000 → Bitiş: ${result['balance']:.2f}")
        print(f"      Net Kar: ${profit:+.2f} ({roi:+.2f}%)")

        print(f"\n   📊 İŞLEM İSTATİSTİKLERİ:")
        print(f"      Toplam: {len(trades)} | Kazanan: {len(winning)} | Kaybeden: {len(losing)}")
        print(f"      Kazanma Oranı: {(len(winning)/len(trades)*100):.1f}%")

        if winning:
            print(f"      Ort. Kazanç: ${np.mean([t['profit'] for t in winning]):.2f}")
        if losing:
            print(f"      Ort. Zarar: ${np.mean([t['profit'] for t in losing]):.2f}")

        # Patern analizi
        entry_patterns = {}
        for t in trades:
            p = t['entry_pattern']
            if p not in entry_patterns:
                entry_patterns[p] = []
            entry_patterns[p].append(t['profit'])

        print(f"\n   🎯 PATERN ANALİZİ:")
        for pattern, profits in entry_patterns.items():
            avg = np.mean(profits)
            count = len(profits)
            print(f"      {pattern:20} → {count:2} işlem, Ort: ${avg:+7.2f}")

    print("\n" + "="*80)
    print("✅ Test tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
