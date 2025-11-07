"""
STRATEJİ TARAYICI - Tüm Stratejileri Toplu Test Et
═══════════════════════════════════════════════════════════
Amaç: Tüm stratejileri otomatik olarak test et ve en iyiyi bul
      - 12 farklı stratejiyi 4 adımlı testten geçir
      - En tutarlı stratejiyi belirle
      - Over-fitting riskini minimize et

Neden: Tek tek test etmek yerine otomatik tarama ile
       en iyi stratejiyi hızlıca bulalım.
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


def load_data_range(start_ts, end_ts):
    """Belirli timestamp aralığı için veri yükle"""
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

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


def run_backtest(df, strategy_config):
    """Stratejiyi backtest et"""
    if len(df) < 100:
        return None

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
    balance_history = [10000]

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
                    trades.append({'profit': profit, 'balance_after': balance})
                    position = None
                else:
                    position = update_result['updated_position']
            else:
                position = update_result['updated_position']

        # Yeni giriş
        if position is None and pattern in entry_patterns and strength >= min_strength:
            qty = (balance * position_size_pct) / price
            position = {
                'entry_price': price,
                'qty': qty,
                'remaining_qty': qty,
                'entry_index': i,
                'entry_fractal_score': fractal_score,
                'tp': price * (1 + tp_pct),
                'sl': price * (1 - sl_pct),
                'stop_loss': price * (1 - sl_pct),
                'trailing_stop': 0,
                'partial_exits': []
            }

        balance_history.append(balance)

    # Drawdown hesapla
    balance_array = np.array(balance_history)
    peak = np.maximum.accumulate(balance_array)
    drawdown = ((balance_array - peak) / peak) * 100
    max_drawdown = drawdown.min()

    return {
        'balance': balance,
        'trades': trades,
        'profit': balance - 10000,
        'roi': ((balance - 10000) / 10000) * 100,
        'max_drawdown': max_drawdown
    }


def score_strategy(strategy_config):
    """Stratejiyi 4 adımlı testle puanla"""

    # ADIM 1: Multi-year test (2023 vs 2024)
    print(f"   [1/4] Multi-year test...", end='', flush=True)

    df_2023 = load_data_range(1672531200000, 1704067199000)  # 2023
    df_2024 = load_data_range(1704067200000, 1735689599000)  # 2024

    result_2023 = run_backtest(df_2023, strategy_config)
    result_2024 = run_backtest(df_2024, strategy_config)

    if result_2023 is None or result_2024 is None:
        print(" BAŞARISIZ (veri yetersiz)")
        return None

    # Her iki yıl da pozitif mi?
    both_positive = result_2023['roi'] > 0 and result_2024['roi'] > 0
    consistency_score = 100 if both_positive else 0

    print(f" ✓ (2023: {result_2023['roi']:+.1f}%, 2024: {result_2024['roi']:+.1f}%)")

    # ADIM 2: Position size check (Max drawdown kontrolü)
    print(f"   [2/4] Drawdown check...", end='', flush=True)

    avg_dd = (result_2023['max_drawdown'] + result_2024['max_drawdown']) / 2

    # Drawdown skorlaması (mutlak değer < 30% = iyi)
    if abs(avg_dd) < 20:
        dd_score = 100
    elif abs(avg_dd) < 30:
        dd_score = 70
    elif abs(avg_dd) < 50:
        dd_score = 40
    else:
        dd_score = 0

    print(f" ✓ (Avg DD: {avg_dd:.1f}%)")

    # ADIM 3: Win rate ve trade sayısı
    print(f"   [3/4] Trade quality...", end='', flush=True)

    all_trades = result_2023['trades'] + result_2024['trades']

    if len(all_trades) == 0:
        print(" BAŞARISIZ (işlem yok)")
        return None

    winning = [t for t in all_trades if t['profit'] > 0]
    win_rate = (len(winning) / len(all_trades)) * 100

    # Win rate skorlaması
    if win_rate >= 55:
        wr_score = 100
    elif win_rate >= 50:
        wr_score = 80
    elif win_rate >= 45:
        wr_score = 60
    else:
        wr_score = 40

    print(f" ✓ (Win: {win_rate:.1f}%, Trades: {len(all_trades)})")

    # ADIM 4: Walk-forward (quarterly consistency)
    print(f"   [4/4] Walk-forward...", end='', flush=True)

    # 6 aylık periyotlar
    quarters = [
        (1672531200000, 1687910400000),  # 2023 H1
        (1687910400000, 1704067199000),  # 2023 H2
        (1704067200000, 1719792000000),  # 2024 H1
        (1719792000000, 1735689599000),  # 2024 H2
    ]

    quarterly_rois = []
    for start, end in quarters:
        df = load_data_range(start, end)
        result = run_backtest(df, strategy_config)
        if result:
            quarterly_rois.append(result['roi'])

    if len(quarterly_rois) < 2:
        wf_score = 0
    else:
        positive_quarters = [r for r in quarterly_rois if r > 0]
        wf_consistency = (len(positive_quarters) / len(quarterly_rois)) * 100

        # Walk-forward skorlaması
        if wf_consistency >= 75:
            wf_score = 100
        elif wf_consistency >= 50:
            wf_score = 70
        elif wf_consistency >= 25:
            wf_score = 40
        else:
            wf_score = 0

    print(f" ✓ ({len(positive_quarters)}/{len(quarterly_rois)} positive)")

    # TOPLAM SKOR (weighted average)
    total_score = (
        consistency_score * 0.35 +  # 35% - Her iki yıl da pozitif
        dd_score * 0.25 +            # 25% - Drawdown kontrolü
        wr_score * 0.20 +            # 20% - Win rate
        wf_score * 0.20              # 20% - Walk-forward tutarlılık
    )

    return {
        'total_score': total_score,
        'consistency_score': consistency_score,
        'dd_score': dd_score,
        'wr_score': wr_score,
        'wf_score': wf_score,
        'roi_2023': result_2023['roi'],
        'roi_2024': result_2024['roi'],
        'avg_dd': avg_dd,
        'win_rate': win_rate,
        'num_trades': len(all_trades),
        'wf_positive': f"{len(positive_quarters)}/{len(quarterly_rois)}"
    }


# TÜM STRATEJİLER
all_strategies = [
    # ADVANCED STRATEGIES (advanced_strategy_tester.py'den)
    {
        'name': 'Trailing Stop Master',
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'min_strength': 35,
        'position_size': 0.15,
        'tp_percent': 0.25,
        'sl_percent': 0.08,
        'weights': {'TRENDING_UP': 3.0, 'OUTSIDE_BAR': 3.5, 'TRENDING_DOWN': 2.0, 'INSIDE_BAR': 0.3},
        'trade_management': {
            'use_trailing_stop': True,
            'trailing_stop_activation': 5.0,
            'trailing_stop_distance': 3.0,
            'use_breakeven': True,
            'breakeven_activation': 3.0,
            'breakeven_offset': 0.5,
            'use_partial_exit': False,
            'use_momentum_exit': False,
            'use_time_exit': False
        }
    },

    {
        'name': 'Momentum Guardian',
        'entry_patterns': ['Trending Up'],
        'min_strength': 40,
        'position_size': 0.12,
        'tp_percent': 0.20,
        'sl_percent': 0.07,
        'weights': {'TRENDING_UP': 4.0, 'TRENDING_DOWN': 3.0, 'OUTSIDE_BAR': 2.0, 'INSIDE_BAR': 0.2},
        'trade_management': {
            'use_momentum_exit': True,
            'momentum_threshold': 40,
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

    {
        'name': 'Conservative Protection',
        'entry_patterns': ['Trending Up'],
        'min_strength': 45,
        'position_size': 0.08,
        'tp_percent': 0.15,
        'sl_percent': 0.05,
        'weights': {'TRENDING_UP': 3.5, 'TRENDING_DOWN': 3.0, 'OUTSIDE_BAR': 1.5, 'INSIDE_BAR': 0.2},
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
    },
]


def main():
    """Ana tarama fonksiyonu"""
    print("="*80)
    print("STRATEJİ TARAYICI - TOPLU TEST")
    print("="*80)
    print(f"\n🔍 {len(all_strategies)} strateji test edilecek")
    print("📊 Her strateji 4 adımlı testten geçirilecek:")
    print("   1. Multi-year test (2023 vs 2024)")
    print("   2. Drawdown kontrolü")
    print("   3. Trade kalitesi (Win rate)")
    print("   4. Walk-forward tutarlılık")
    print("\n" + "="*80 + "\n")

    results = []

    for i, strategy in enumerate(all_strategies, 1):
        print(f"[{i}/{len(all_strategies)}] {strategy['name']}")

        score = score_strategy(strategy)

        if score is None:
            print(f"   ❌ BAŞARISIZ\n")
            continue

        score['name'] = strategy['name']
        results.append(score)

        print(f"   📊 SKOR: {score['total_score']:.1f}/100\n")

    # SONUÇLARI SIRALA
    results_sorted = sorted(results, key=lambda x: x['total_score'], reverse=True)

    # SKOR TABLOSU
    print("="*80)
    print("SONUÇ TABLOSU (En İyiden En Kötüye)")
    print("="*80)
    print(f"\n{'Sıra':<5} {'Strateji':<30} {'SKOR':<10} {'2023':<10} {'2024':<10} {'DD':<10}")
    print("─" * 80)

    for i, r in enumerate(results_sorted, 1):
        marker = "🏆" if i == 1 else "⭐" if i <= 3 else "  "
        print(f"{i:<5} {r['name']:<30} {r['total_score']:>5.1f}/100  "
              f"{r['roi_2023']:>6.1f}%  {r['roi_2024']:>6.1f}%  {r['avg_dd']:>6.1f}% {marker}")

    # EN İYİ STRATEJİ DETAYI
    if results_sorted:
        best = results_sorted[0]

        print("\n" + "="*80)
        print("🏆 EN İYİ STRATEJİ")
        print("="*80)
        print(f"\n📌 {best['name']}")
        print(f"   Toplam Skor: {best['total_score']:.1f}/100\n")
        print(f"   📊 DETAY SKORLARI:")
        print(f"      Multi-year Consistency: {best['consistency_score']:.0f}/100")
        print(f"      Drawdown Control: {best['dd_score']:.0f}/100")
        print(f"      Win Rate Quality: {best['wr_score']:.0f}/100")
        print(f"      Walk-forward: {best['wf_score']:.0f}/100\n")
        print(f"   💰 PERFORMANS:")
        print(f"      2023 ROI: {best['roi_2023']:+.2f}%")
        print(f"      2024 ROI: {best['roi_2024']:+.2f}%")
        print(f"      Avg Drawdown: {best['avg_dd']:.2f}%")
        print(f"      Win Rate: {best['win_rate']:.1f}%")
        print(f"      Total Trades: {best['num_trades']}")
        print(f"      Walk-forward: {best['wf_positive']} quarters positive")

        if best['total_score'] >= 70:
            print("\n   ✅ Bu strateji gerçek trade için UYGUNDUR!")
        elif best['total_score'] >= 50:
            print("\n   ⚠️  Bu strateji daha fazla test gerektirir")
        else:
            print("\n   ❌ Bu strateji daha fazla optimizasyon gerektirir")

    print("\n" + "="*80)
    print("✅ Tarama tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
