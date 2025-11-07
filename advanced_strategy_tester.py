"""
Gelişmiş Strateji Test Motoru
Trailing stop, partial exit, momentum exit ile
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
from datetime import datetime
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from advanced_trade_manager import TradeManager
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


def backtest_advanced_strategy(df, strategy_config):
    """
    Gelişmiş strateji backtest motoru
    """
    # Fraktal analiz
    df = FractalAnalyzer.analyze_series(df)
    analyzer = MultiTimeframeFractalAnalyzer(weights=strategy_config.get('weights'))
    df = analyzer.calculate_fractal_score(df)

    # Trade manager
    trade_manager = TradeManager(strategy_config['trade_management'])

    # Backtest
    balance = 10000
    position = None
    trades = []
    partial_exits = []

    entry_patterns = strategy_config['entry_patterns']
    min_strength = strategy_config['min_strength']
    position_size_pct = strategy_config['position_size']
    tp_pct = strategy_config['tp_percent']
    sl_pct = strategy_config['sl_percent']

    for i in range(50, len(df)):
        row = df.iloc[i]
        price = row['close']
        pattern = row.get('fractal_pattern')
        strength = row.get('fractal_strength', 0)
        fractal_score = row.get('fractal_score', 0)

        # Mevcut pozisyon varsa güncelle
        if position is not None:
            update_result = trade_manager.update_position(
                position, price, i, fractal_score
            )

            # Çıkış gerekiyor mu?
            if update_result['action'] == 'exit_full':
                # Tam çıkış
                qty = update_result['exit_qty']
                profit = (price - position['entry_price']) * qty
                balance += profit

                trades.append({
                    'entry_price': position['entry_price'],
                    'exit_price': price,
                    'profit': profit,
                    'qty': qty,
                    'exit_reason': update_result['exit_reason'],
                    'bars_held': i - position['entry_index'],
                    'partial_exits': position.get('partial_exits', [])
                })

                position = None

            elif update_result['action'] == 'exit_partial':
                # Kısmi çıkış
                qty = update_result['exit_qty']
                profit = (price - position['entry_price']) * qty
                balance += profit

                partial_exits.append({
                    'price': price,
                    'qty': qty,
                    'profit': profit,
                    'reason': update_result['exit_reason']
                })

                # Pozisyonu güncelle
                position = update_result['updated_position']

            else:
                # Pozisyonu güncelle (trailing stop, breakeven vs.)
                position = update_result['updated_position']

        # Yeni giriş sinyali
        if position is None and pattern in entry_patterns and strength >= min_strength:
            qty = (balance * position_size_pct) / price
            position = {
                'entry_price': price,
                'qty': qty,
                'remaining_qty': qty,
                'entry_index': i,
                'entry_pattern': pattern,
                'entry_strength': strength,
                'entry_fractal_score': fractal_score,
                'tp': price * (1 + tp_pct),
                'sl': price * (1 - sl_pct),
                'stop_loss': price * (1 - sl_pct),
                'trailing_stop': 0,
                'partial_exits': [],
                'completed_partial_levels': set()
            }

    return {
        'balance': balance,
        'trades': trades,
        'partial_exits': partial_exits,
        'strategy_name': strategy_config['name']
    }


# GELİŞMİŞ STRATEJİ VARYASYONLARI
advanced_strategies = [
    # 1. Trailing Stop Master
    {
        'name': 'Trailing Stop Master',
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'min_strength': 35,
        'position_size': 0.15,
        'tp_percent': 0.25,
        'sl_percent': 0.08,
        'weights': {
            'TRENDING_UP': 3.0,
            'OUTSIDE_BAR': 3.5,
            'TRENDING_DOWN': 2.0,
            'INSIDE_BAR': 0.3
        },
        'trade_management': {
            'use_trailing_stop': True,
            'trailing_stop_activation': 5.0,   # %5 kârda aktif
            'trailing_stop_distance': 3.0,     # %3 mesafe

            'use_breakeven': True,
            'breakeven_activation': 3.0,        # %3'te breakeven'e al
            'breakeven_offset': 0.5,           # +%0.5 offset

            'use_partial_exit': False,
            'use_momentum_exit': False,
            'use_time_exit': False
        }
    },

    # 2. Partial Exit Pro
    {
        'name': 'Partial Exit Pro',
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
                {'price_pct': 8.0, 'qty_pct': 0.33},   # %8'de 1/3 sat
                {'price_pct': 15.0, 'qty_pct': 0.33},  # %15'te 1/3 sat
                # Kalan 1/3 TP'de
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
    },

    # 3. Momentum Guardian
    {
        'name': 'Momentum Guardian',
        'entry_patterns': ['Trending Up'],
        'min_strength': 40,
        'position_size': 0.12,
        'tp_percent': 0.20,
        'sl_percent': 0.07,
        'weights': {
            'TRENDING_UP': 4.0,
            'TRENDING_DOWN': 3.0,
            'OUTSIDE_BAR': 2.0,
            'INSIDE_BAR': 0.2
        },
        'trade_management': {
            'use_momentum_exit': True,
            'momentum_threshold': 40,  # Momentum %40 düşerse çık

            'use_trailing_stop': True,
            'trailing_stop_activation': 7.0,
            'trailing_stop_distance': 2.5,

            'use_breakeven': True,
            'breakeven_activation': 4.0,
            'breakeven_offset': 0.8,

            'use_partial_exit': False,
            'use_time_exit': False
        }
    },

    # 4. Time-Based Disciplined
    {
        'name': 'Time-Based Disciplined',
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'min_strength': 30,
        'position_size': 0.10,
        'tp_percent': 0.18,
        'sl_percent': 0.06,
        'weights': {
            'TRENDING_UP': 2.5,
            'OUTSIDE_BAR': 2.5,
            'TRENDING_DOWN': 2.0,
            'INSIDE_BAR': 0.5
        },
        'trade_management': {
            'use_time_exit': True,
            'max_hold_bars': 72,  # Max 72 saat (3 gün) tut

            'use_trailing_stop': True,
            'trailing_stop_activation': 6.0,
            'trailing_stop_distance': 3.0,

            'use_breakeven': True,
            'breakeven_activation': 3.5,
            'breakeven_offset': 0.5,

            'use_partial_exit': False,
            'use_momentum_exit': False
        }
    },

    # 5. Full Arsenal (Hepsini kullan)
    {
        'name': 'Full Arsenal (All Features)',
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'min_strength': 35,
        'position_size': 0.15,
        'tp_percent': 0.25,
        'sl_percent': 0.08,
        'weights': {
            'TRENDING_UP': 3.0,
            'OUTSIDE_BAR': 3.0,
            'TRENDING_DOWN': 2.5,
            'INSIDE_BAR': 0.3
        },
        'trade_management': {
            'use_trailing_stop': True,
            'trailing_stop_activation': 6.0,
            'trailing_stop_distance': 2.5,

            'use_partial_exit': True,
            'partial_exit_levels': [
                {'price_pct': 10.0, 'qty_pct': 0.5},  # %10'da yarısını sat
            ],

            'use_breakeven': True,
            'breakeven_activation': 4.0,
            'breakeven_offset': 0.5,

            'use_momentum_exit': True,
            'momentum_threshold': 50,

            'use_time_exit': True,
            'max_hold_bars': 100
        }
    },

    # 6. Conservative Protection
    {
        'name': 'Conservative Protection',
        'entry_patterns': ['Trending Up'],
        'min_strength': 45,
        'position_size': 0.08,
        'tp_percent': 0.15,
        'sl_percent': 0.05,
        'weights': {
            'TRENDING_UP': 3.5,
            'TRENDING_DOWN': 3.0,
            'OUTSIDE_BAR': 1.5,
            'INSIDE_BAR': 0.2
        },
        'trade_management': {
            'use_trailing_stop': True,
            'trailing_stop_activation': 4.0,
            'trailing_stop_distance': 2.0,

            'use_breakeven': True,
            'breakeven_activation': 2.5,
            'breakeven_offset': 0.3,

            'use_partial_exit': True,
            'partial_exit_levels': [
                {'price_pct': 5.0, 'qty_pct': 0.33},
                {'price_pct': 10.0, 'qty_pct': 0.33},
            ],

            'use_momentum_exit': True,
            'momentum_threshold': 60,

            'use_time_exit': False
        }
    }
]


def main():
    """Ana test fonksiyonu"""
    print("="*80)
    print("GELİŞMİŞ STRATEJİ TEST MOTORU")
    print("="*80)
    print("\n🚀 YENİ ÖZELLİKLER:")
    print("  1. ⚡ Trailing Stop Loss   - Dinamik stop yönetimi")
    print("  2. 📊 Partial Exit         - Kademeli kar realizasyonu")
    print("  3. 💪 Momentum Exit        - Momentum kaybında çıkış")
    print("  4. ⏰ Time-Based Exit      - Süre bazlı disiplin")
    print("  5. 🎯 Breakeven Stop       - Riski sıfırla")
    print("\n" + "="*80)

    # Veri yükle
    print("\n📊 Veri yükleniyor...")
    df = load_data()
    print(f"✅ {len(df)} mum yüklendi")

    # Stratejileri test et
    results = []

    print(f"\n🧪 {len(advanced_strategies)} gelişmiş strateji test ediliyor...\n")

    for i, strategy in enumerate(advanced_strategies, 1):
        print(f"⏳ [{i}/{len(advanced_strategies)}] {strategy['name']}...")
        result = backtest_advanced_strategy(df, strategy)
        results.append(result)

    # Sonuçları sırala
    results_sorted = sorted(results, key=lambda x: x['balance'], reverse=True)

    # KARŞILAŞTIRMA TABLOSU
    print("\n" + "="*80)
    print("SONUÇ KARŞILAŞTIRMASI")
    print("="*80)
    print(f"\n{'Sıra':<5} {'Strateji':<35} {'Getiri':<12} {'İşlem':<8} {'Kazanma':<10}")
    print("─" * 80)

    for i, result in enumerate(results_sorted, 1):
        profit = result['balance'] - 10000
        roi = (profit / 10000) * 100
        trades = result['trades']

        if len(trades) > 0:
            winning = [t for t in trades if t['profit'] > 0]
            win_rate = (len(winning) / len(trades)) * 100
        else:
            win_rate = 0

        print(f"{i:<5} {result['strategy_name']:<35} {roi:+6.2f}%{'':<5} {len(trades):<8} {win_rate:>5.1f}%")

    # EN İYİ 3 STRATEJİ DETAYLI ANALİZ
    print("\n" + "="*80)
    print("🏆 EN İYİ 3 STRATEJİ - DETAYLI ANALİZ")
    print("="*80)

    for rank, result in enumerate(results_sorted[:3], 1):
        trades = result['trades']
        if len(trades) == 0:
            continue

        winning = [t for t in trades if t['profit'] > 0]
        losing = [t for t in trades if t['profit'] < 0]

        profit = result['balance'] - 10000
        roi = (profit / 10000) * 100

        print(f"\n{rank}. {result['strategy_name']}")
        print("─" * 80)

        print(f"   💰 FİNANSAL:")
        print(f"      Net Kar: ${profit:+.2f} ({roi:+.2f}%)")
        print(f"      Final Balance: ${result['balance']:.2f}")

        print(f"\n   📊 İŞLEM İSTATİSTİKLERİ:")
        print(f"      Toplam İşlem: {len(trades)}")
        print(f"      Kazanan: {len(winning)} | Kaybeden: {len(losing)}")
        print(f"      Kazanma Oranı: {(len(winning)/len(trades)*100):.1f}%")

        if winning:
            avg_win = np.mean([t['profit'] for t in winning])
            max_win = max([t['profit'] for t in winning])
            print(f"      Ort. Kazanç: ${avg_win:.2f} | Max: ${max_win:.2f}")

        if losing:
            avg_loss = np.mean([t['profit'] for t in losing])
            max_loss = min([t['profit'] for t in losing])
            print(f"      Ort. Zarar: ${avg_loss:.2f} | Max: ${max_loss:.2f}")

        # Çıkış sebepleri
        exit_reasons = {}
        for t in trades:
            reason = t['exit_reason']
            if reason not in exit_reasons:
                exit_reasons[reason] = {'count': 0, 'total_profit': 0}
            exit_reasons[reason]['count'] += 1
            exit_reasons[reason]['total_profit'] += t['profit']

        print(f"\n   🎯 ÇIKIŞ SEBEPLERİ:")
        for reason, stats in sorted(exit_reasons.items(), key=lambda x: x[1]['count'], reverse=True):
            avg = stats['total_profit'] / stats['count']
            print(f"      {reason:25} → {stats['count']:3} işlem, Ort: ${avg:+7.2f}")

        # Ortalama tutma süresi
        avg_bars = np.mean([t['bars_held'] for t in trades])
        print(f"\n   ⏰ ORTALAMA TUTMA SÜRESİ: {avg_bars:.1f} saat")

        # Partial exit istatistikleri
        total_partials = sum(len(t.get('partial_exits', [])) for t in trades)
        if total_partials > 0:
            print(f"   📊 PARTIAL EXIT: {total_partials} kez kısmi çıkış yapıldı")

    print("\n" + "="*80)
    print("✅ Test tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
