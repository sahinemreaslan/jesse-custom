"""
TRAILING STOP MASTER - OPTİMİZASYON VE DETAYLI ANALİZ
═══════════════════════════════════════════════════════════
Amaç: 100/100 skor alan Trailing Stop Master stratejisini
      4 adımlı testten geçir ve optimize et

Strateji Özellikleri:
  - Giriş: Trending Up, Outside Bar
  - Min Strength: 35
  - Position Size: %15
  - Trailing Stop: %5'te aktif, %3 mesafe
  - Breakeven: %3'te aktif
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


# BASE STRATEJİ
BASE_STRATEGY = {
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
        'trailing_stop_activation': 5.0,
        'trailing_stop_distance': 3.0,
        'use_breakeven': True,
        'breakeven_activation': 3.0,
        'breakeven_offset': 0.5,
        'use_partial_exit': False,
        'use_momentum_exit': False,
        'use_time_exit': False
    }
}


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


def run_backtest(df, config):
    """Backtest çalıştır"""
    if len(df) < 100:
        return None

    # Fraktal analiz
    df = FractalAnalyzer.analyze_series(df)
    analyzer = MultiTimeframeFractalAnalyzer(weights=config['weights'])
    df = analyzer.calculate_fractal_score(df)

    # Trade manager
    trade_manager = TradeManager(config['trade_management'])

    # Backtest
    balance = 10000
    position = None
    trades = []
    balance_history = [10000]

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


def main():
    """Ana test fonksiyonu"""
    print("="*80)
    print("TRAILING STOP MASTER - DETAYLI ANALİZ")
    print("="*80)
    print("\n🏆 Scanner Skoru: 100/100")
    print("📊 Beklenen: Tutarlı, düşük drawdown, yüksek win rate")
    print("\n" + "="*80)

    # ADIM 1: MULTI-YEAR TEST
    print("\n📅 ADIM 1: MULTI-YEAR TEST")
    print("─" * 80)

    df_2023 = load_data_range(1672531200000, 1704067199000)
    df_2024 = load_data_range(1704067200000, 1735689599000)

    print(f"\n⏳ 2023 testi...")
    result_2023 = run_backtest(df_2023, BASE_STRATEGY)

    print(f"⏳ 2024 testi...")
    result_2024 = run_backtest(df_2024, BASE_STRATEGY)

    print(f"\n{'Periyot':<20} {'Getiri':<12} {'İşlem':<10} {'Max DD':<12}")
    print("─" * 80)
    print(f"{'2023':<20} {result_2023['roi']:>6.2f}%{'':<5} {len(result_2023['trades']):<10} {result_2023['max_drawdown']:>6.2f}%")
    print(f"{'2024':<20} {result_2024['roi']:>6.2f}%{'':<5} {len(result_2024['trades']):<10} {result_2024['max_drawdown']:>6.2f}%")

    both_positive = result_2023['roi'] > 0 and result_2024['roi'] > 0
    print(f"\n{'✅ Her iki yıl da pozitif!' if both_positive else '❌ Tutarsızlık var!'}")

    # ADIM 2: WALK-FORWARD
    print("\n" + "="*80)
    print("📊 ADIM 2: WALK-FORWARD TEST (Çeyreklik)")
    print("─" * 80)

    quarters = [
        ('2023 Q1', 1672531200000, 1680307199000),
        ('2023 Q2', 1680307200000, 1688169599000),
        ('2023 Q3', 1688169600000, 1696118399000),
        ('2023 Q4', 1696118400000, 1704067199000),
        ('2024 Q1', 1704067200000, 1711929599000),
        ('2024 Q2', 1711929600000, 1719791999000),
        ('2024 Q3', 1719792000000, 1727827199000),
        ('2024 Q4', 1727827200000, 1735689599000),
    ]

    quarterly_results = []
    for name, start, end in quarters:
        df = load_data_range(start, end)
        result = run_backtest(df, BASE_STRATEGY)
        if result:
            quarterly_results.append({
                'name': name,
                'roi': result['roi'],
                'trades': len(result['trades']),
                'dd': result['max_drawdown']
            })

    print(f"\n{'Çeyrek':<15} {'Getiri':<12} {'İşlem':<10} {'Max DD':<12}")
    print("─" * 80)
    for r in quarterly_results:
        marker = "✅" if r['roi'] > 0 else "❌"
        print(f"{r['name']:<15} {r['roi']:>6.2f}%{'':<5} {r['trades']:<10} {r['dd']:>6.2f}%  {marker}")

    positive_quarters = [r for r in quarterly_results if r['roi'] > 0]
    consistency = len(positive_quarters) / len(quarterly_results) * 100
    print(f"\n📈 Tutarlılık: {len(positive_quarters)}/{len(quarterly_results)} çeyrek pozitif ({consistency:.1f}%)")

    # ADIM 3: TRADE ANALİZİ
    print("\n" + "="*80)
    print("🎯 ADIM 3: TRADE KALITE ANALİZİ")
    print("─" * 80)

    all_trades = result_2023['trades'] + result_2024['trades']
    winning = [t for t in all_trades if t['profit'] > 0]
    losing = [t for t in all_trades if t['profit'] < 0]

    print(f"\n💰 İŞLEM İSTATİSTİKLERİ:")
    print(f"   Toplam İşlem: {len(all_trades)}")
    print(f"   Kazanan: {len(winning)} ({len(winning)/len(all_trades)*100:.1f}%)")
    print(f"   Kaybeden: {len(losing)} ({len(losing)/len(all_trades)*100:.1f}%)")

    if winning:
        avg_win = np.mean([t['profit'] for t in winning])
        print(f"   Ort. Kazanç: ${avg_win:.2f}")

    if losing:
        avg_loss = np.mean([t['profit'] for t in losing])
        print(f"   Ort. Zarar: ${avg_loss:.2f}")

    # Çıkış sebepleri
    exit_reasons = {}
    for t in all_trades:
        reason = t['exit_reason']
        if reason not in exit_reasons:
            exit_reasons[reason] = 0
        exit_reasons[reason] += 1

    print(f"\n🎯 ÇIKIŞ SEBEPLERİ:")
    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(all_trades)) * 100
        print(f"   {reason:25} → {count:3} işlem ({pct:.1f}%)")

    # ADIM 4: RİSK ANALİZİ
    print("\n" + "="*80)
    print("⚖️  ADIM 4: RİSK METRİKLERİ")
    print("─" * 80)

    avg_roi = (result_2023['roi'] + result_2024['roi']) / 2
    avg_dd = (result_2023['max_drawdown'] + result_2024['max_drawdown']) / 2

    total_profit = sum([t['profit'] for t in all_trades])
    total_win = sum([t['profit'] for t in winning])
    total_loss = abs(sum([t['profit'] for t in losing])) if losing else 1

    profit_factor = total_win / total_loss if total_loss > 0 else float('inf')
    expectancy = np.mean([t['profit'] for t in all_trades])

    print(f"\n📊 PERFORMANS:")
    print(f"   Ortalama ROI: {avg_roi:+.2f}%")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"   Expectancy: ${expectancy:.2f}/trade")

    print(f"\n🛡️  RİSK:")
    print(f"   Ortalama Max DD: {avg_dd:.2f}%")
    print(f"   Recovery Factor: {(result_2023['profit'] + result_2024['profit']) / abs(avg_dd * 10000 / 100):.2f}")

    # FINAL SKOR
    print("\n" + "="*80)
    print("📋 FINAL DEĞERLENDİRME")
    print("="*80)

    score_items = []

    # Multi-year consistency
    if both_positive:
        score_items.append("✅ Multi-year consistency (Her iki yıl da pozitif)")
    else:
        score_items.append("❌ Multi-year consistency")

    # Walk-forward
    if consistency >= 75:
        score_items.append(f"✅ Walk-forward consistency ({consistency:.0f}% pozitif)")
    else:
        score_items.append(f"⚠️  Walk-forward consistency ({consistency:.0f}% pozitif)")

    # Drawdown
    if abs(avg_dd) < 5:
        score_items.append(f"✅ Mükemmel drawdown kontrolü ({avg_dd:.1f}%)")
    elif abs(avg_dd) < 10:
        score_items.append(f"✅ İyi drawdown kontrolü ({avg_dd:.1f}%)")
    else:
        score_items.append(f"⚠️  Orta drawdown ({avg_dd:.1f}%)")

    # Win rate
    win_rate = len(winning) / len(all_trades) * 100
    if win_rate >= 60:
        score_items.append(f"✅ Yüksek win rate ({win_rate:.1f}%)")
    elif win_rate >= 50:
        score_items.append(f"✅ İyi win rate ({win_rate:.1f}%)")
    else:
        score_items.append(f"⚠️  Orta win rate ({win_rate:.1f}%)")

    # Profit factor
    if profit_factor >= 2.0:
        score_items.append(f"✅ Mükemmel profit factor ({profit_factor:.2f})")
    elif profit_factor >= 1.5:
        score_items.append(f"✅ İyi profit factor ({profit_factor:.2f})")
    else:
        score_items.append(f"⚠️  Orta profit factor ({profit_factor:.2f})")

    print("\n📊 SKORLAR:\n")
    for item in score_items:
        print(f"   {item}")

    passed = sum(1 for item in score_items if item.startswith("✅"))
    total = len(score_items)

    final_score = (passed / total) * 100

    print(f"\n{'='*80}")
    print(f"TOPLAM SKOR: {passed}/{total} ({final_score:.0f}%)")
    print(f"{'='*80}")

    if final_score >= 80:
        print("\n✅ STRATEJİ ONAYLANDI - Gerçek trade için hazır!")
    elif final_score >= 60:
        print("\n⚠️  STRATEJİ İYİ - Daha fazla optimizasyon önerilir")
    else:
        print("\n❌ STRATEJİ YETERSİZ - Daha fazla çalışma gerekli")

    print("\n" + "="*80)
    print("✅ Analiz tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
