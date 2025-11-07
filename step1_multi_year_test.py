"""
ADIM 1: ÇOKLU YIL TESTİ
═══════════════════════════════════════════════════════════
Amaç: Partial Exit Pro stratejisini farklı dönemlerde test et
       - 2023 yılı
       - 2024 yılı
       - 2023-2024 toplam

Neden: Strateji sadece bir yılda iyi çalışıyor mu yoksa tutarlı mı?
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from advanced_trade_manager import TradeManager


def load_data_for_period(start_date: str, end_date: str):
    """Belirli dönem için veri yükle"""
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

    # Tarihleri timestamp'e çevir
    start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)

    query = f'''
        SELECT timestamp, open, high, low, close, volume
        FROM candle
        WHERE exchange = 'Binance Futures'
          AND symbol = 'BTC-USDT'
          AND timeframe = '1h'
          AND timestamp >= {start_ts}
          AND timestamp <= {end_ts}
        ORDER BY timestamp ASC;
    '''

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def run_backtest(df, initial_balance=10000):
    """Partial Exit Pro stratejisini çalıştır"""
    # Strateji konfigürasyonu (Partial Exit Pro)
    config = {
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'min_strength': 30,
        'position_size': 0.20,
        'tp_percent': 0.30,
        'sl_percent': 0.10,
        'weights': {
            'TRENDING_UP': 2.5,
            'OUTSIDE_BAR': 3.0,
            'TRENDING_DOWN': 2.0,
            'INSIDE_BAR': 0.5
        },
        'trade_management': {
            'use_partial_exit': True,
            'partial_exit_levels': [
                {'price_pct': 8.0, 'qty_pct': 0.33},
                {'price_pct': 15.0, 'qty_pct': 0.33},
            ],
            'use_trailing_stop': True,
            'trailing_stop_activation': 10.0,
            'trailing_stop_distance': 4.0,
            'use_breakeven': True,
            'breakeven_activation': 5.0,
            'breakeven_offset': 1.0,
            'use_momentum_exit': False,
            'use_time_exit': False
        }
    }

    # Fraktal analiz
    df = FractalAnalyzer.analyze_series(df)
    analyzer = MultiTimeframeFractalAnalyzer(weights=config['weights'])
    df = analyzer.calculate_fractal_score(df)

    # Trade manager
    trade_manager = TradeManager(config['trade_management'])

    # Backtest
    balance = initial_balance
    position = None
    trades = []

    for i in range(50, len(df)):
        row = df.iloc[i]
        price = row['close']
        pattern = row.get('fractal_pattern')
        strength = row.get('fractal_strength', 0)
        fractal_score = row.get('fractal_score', 0)

        # Pozisyon güncelleme
        if position is not None:
            update_result = trade_manager.update_position(
                position, price, i, fractal_score
            )

            if update_result['action'] in ['exit_full', 'exit_partial']:
                qty = update_result['exit_qty']
                profit = (price - position['entry_price']) * qty
                balance += profit

                if update_result['action'] == 'exit_full':
                    trades.append({
                        'profit': profit,
                        'exit_reason': update_result['exit_reason'],
                        'bars_held': i - position['entry_index']
                    })
                    position = None
                else:
                    position = update_result['updated_position']
            else:
                position = update_result['updated_position']

        # Yeni giriş
        if position is None and pattern in config['entry_patterns'] and strength >= config['min_strength']:
            qty = (balance * config['position_size']) / price
            position = {
                'entry_price': price,
                'qty': qty,
                'remaining_qty': qty,
                'entry_index': i,
                'entry_fractal_score': fractal_score,
                'tp': price * (1 + config['tp_percent']),
                'sl': price * (1 - config['sl_percent']),
                'stop_loss': price * (1 - config['sl_percent']),
                'trailing_stop': 0,
                'partial_exits': []
            }

    return {
        'balance': balance,
        'trades': trades,
        'profit': balance - initial_balance,
        'roi': ((balance - initial_balance) / initial_balance) * 100
    }


def main():
    """Ana test fonksiyonu"""
    print("="*80)
    print("ADIM 1: ÇOKLU YIL TESTİ")
    print("="*80)
    print("\nStrateji: Partial Exit Pro (En başarılı strateji)")
    print("\nTest Periyotları:")
    print("  1. 2023 Yılı (Referans)")
    print("  2. 2024 Yılı (Validasyon)")
    print("  3. 2023-2024 Toplam (Genel Performans)")
    print("\n" + "="*80)

    # Test periyotları
    periods = [
        {'name': '2023 Yılı', 'start': '2023-01-01', 'end': '2023-12-31'},
        {'name': '2024 Yılı', 'start': '2024-01-01', 'end': '2024-12-31'},
        {'name': '2023-2024 Toplam', 'start': '2023-01-01', 'end': '2024-12-31'},
    ]

    results = []

    for period in periods:
        print(f"\n⏳ Test ediliyor: {period['name']}...")

        # Veri yükle
        df = load_data_for_period(period['start'], period['end'])

        if len(df) == 0:
            print(f"   ⚠️  Veri bulunamadı!")
            continue

        print(f"   📊 {len(df)} mum yüklendi")

        # Backtest çalıştır
        result = run_backtest(df)
        result['period'] = period['name']
        result['num_candles'] = len(df)
        results.append(result)

    # SONUÇLARI GÖSTER
    print("\n" + "="*80)
    print("SONUÇLAR")
    print("="*80)

    print(f"\n{'Periyot':<25} {'Getiri':<15} {'İşlem':<10} {'Ort/İşlem':<15}")
    print("─" * 80)

    for result in results:
        num_trades = len(result['trades'])
        avg_per_trade = result['profit'] / num_trades if num_trades > 0 else 0

        print(f"{result['period']:<25} {result['roi']:>6.2f}%{'':<8} "
              f"{num_trades:<10} ${avg_per_trade:>9.2f}")

    # DETAYLI ANALİZ
    print("\n" + "="*80)
    print("DETAYLI ANALİZ")
    print("="*80)

    for result in results:
        trades = result['trades']
        if len(trades) == 0:
            continue

        winning = [t for t in trades if t['profit'] > 0]
        losing = [t for t in trades if t['profit'] < 0]

        print(f"\n📊 {result['period']}")
        print("─" * 80)
        print(f"   Başlangıç: $10,000 → Bitiş: ${result['balance']:.2f}")
        print(f"   Net Kar: ${result['profit']:+.2f} ({result['roi']:+.2f}%)")
        print(f"   Toplam İşlem: {len(trades)}")

        if len(trades) > 0:
            print(f"   Kazanan: {len(winning)} | Kaybeden: {len(losing)}")
            print(f"   Kazanma Oranı: {(len(winning)/len(trades)*100):.1f}%")

            if winning:
                print(f"   Ort. Kazanç: ${np.mean([t['profit'] for t in winning]):.2f}")
            if losing:
                print(f"   Ort. Zarar: ${np.mean([t['profit'] for t in losing]):.2f}")

    # TUTARLıLıK DEĞERLENDİRMESİ
    print("\n" + "="*80)
    print("📈 TUTARLILIK DEĞERLENDİRMESİ")
    print("="*80)

    if len(results) >= 2:
        roi_2023 = results[0]['roi']
        roi_2024 = results[1]['roi'] if len(results) > 1 else 0

        print(f"\n2023 Getiri: {roi_2023:+.2f}%")
        print(f"2024 Getiri: {roi_2024:+.2f}%")

        if roi_2023 > 0 and roi_2024 > 0:
            print("\n✅ SONUÇ: Strateji her iki yılda da KAR ETTİ - TUTARLI")
        elif roi_2023 > 0 and roi_2024 < 0:
            print("\n⚠️  SONUÇ: 2023'te kar, 2024'te zarar - OVER-FİTTİNG RİSKİ")
        elif roi_2023 < 0 and roi_2024 > 0:
            print("\n⚠️  SONUÇ: 2023'te zarar, 2024'te kar - RASTGELE ŞANS")
        else:
            print("\n❌ SONUÇ: Her iki yılda da zarar - STRATEJİ ÇALIŞMIYOR")

    print("\n" + "="*80)
    print("✅ Adım 1 tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
