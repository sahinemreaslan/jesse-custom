"""
FINAL STRATEJİ - TRAILING STOP MASTER (OPTİMİZE EDİLMİŞ)
═══════════════════════════════════════════════════════════
Grid search ile 243 kombinasyon test edildi.
En iyi performans gösteren parametreler seçildi.

📊 OPTİMİZE PARAMETRELERİ:
   - Min Strength: 30
   - TP: 30%
   - SL: 8%
   - Trailing Activation: 5%
   - Trailing Distance: 3.5%

🎯 PERFORMANS:
   - 2023: +17.38% ROI, -2.69% DD
   - 2024: +16.54% ROI, -2.66% DD
   - Tutarlı ve düşük drawdown!

✅ GERÇEK TRADE İÇİN HAZIR
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


# FINAL OPTİMİZE STRATEJİ
FINAL_STRATEGY = {
    'name': 'Trailing Stop Master (Optimized)',
    'entry_patterns': ['Trending Up', 'Outside Bar'],
    'min_strength': 30,  # Grid search sonucu
    'position_size': 0.15,
    'tp_percent': 0.30,  # Grid search: 30%
    'sl_percent': 0.08,  # Grid search: 8%
    'weights': {
        'TRENDING_UP': 3.0,
        'OUTSIDE_BAR': 3.5,
        'TRENDING_DOWN': 2.0,
        'INSIDE_BAR': 0.3
    },
    'trade_management': {
        'use_trailing_stop': True,
        'trailing_stop_activation': 5.0,   # Grid search: 5%
        'trailing_stop_distance': 3.5,     # Grid search: 3.5%
        'use_breakeven': True,
        'breakeven_activation': 3.0,
        'breakeven_offset': 0.5,
        'use_partial_exit': False,
        'use_momentum_exit': False,
        'use_time_exit': False
    }
}


def load_data_range(start_ts, end_ts):
    """Veri yükle"""
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
                        'bars_held': i - position['entry_index'],
                        'balance_after': balance
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

    # Drawdown
    balance_array = np.array(balance_history)
    peak = np.maximum.accumulate(balance_array)
    drawdown = ((balance_array - peak) / peak) * 100
    max_drawdown = drawdown.min()

    return {
        'balance': balance,
        'trades': trades,
        'profit': balance - 10000,
        'roi': ((balance - 10000) / 10000) * 100,
        'max_drawdown': max_drawdown,
        'balance_history': balance_history
    }


def main():
    """Final strateji testi"""
    print("="*80)
    print("FINAL STRATEJİ - TRAILING STOP MASTER (OPTİMİZE)")
    print("="*80)
    print("\n🎯 Grid Search ile 243 kombinasyon test edildi")
    print("✅ En iyi parametreler seçildi\n")
    print("📋 OPTİMİZE PARAMETRELERİ:")
    print("   Min Strength: 30")
    print("   TP: 30%")
    print("   SL: 8%")
    print("   Trailing Activation: 5%")
    print("   Trailing Distance: 3.5%")
    print("\n" + "="*80)

    # FINAL DOĞRULAMA TESTİ
    print("\n📊 FINAL DOĞRULAMA TESTİ")
    print("─" * 80)

    periods = [
        ('2023 Yılı', 1672531200000, 1704067199000),
        ('2024 Yılı', 1704067200000, 1735689599000),
        ('2023-2024 Toplam', 1672531200000, 1735689599000),
    ]

    results = []

    for name, start, end in periods:
        print(f"\n⏳ Test ediliyor: {name}...")
        df = load_data_range(start, end)

        result = run_backtest(df, FINAL_STRATEGY)
        if result:
            result['period'] = name
            results.append(result)
            print(f"   ✅ Tamamlandı: {len(result['trades'])} işlem, {result['roi']:+.2f}% ROI")

    # SONUÇLAR
    print("\n" + "="*80)
    print("📊 FINAL TEST SONUÇLARI")
    print("="*80)

    print(f"\n{'Periyot':<20} {'Getiri':<12} {'İşlem':<10} {'Max DD':<12} {'Avg/Trade':<12}")
    print("─" * 80)

    for r in results:
        avg_trade = r['profit'] / len(r['trades']) if len(r['trades']) > 0 else 0
        print(f"{r['period']:<20} {r['roi']:>6.2f}%{'':<5} {len(r['trades']):<10} "
              f"{r['max_drawdown']:>6.2f}%{'':<5} ${avg_trade:>8.2f}")

    # DETAYLI ANALİZ
    print("\n" + "="*80)
    print("🔍 DETAYLI ANALİZ")
    print("="*80)

    for r in results:
        trades = r['trades']
        if len(trades) == 0:
            continue

        winning = [t for t in trades if t['profit'] > 0]
        losing = [t for t in trades if t['profit'] < 0]

        print(f"\n📌 {r['period']}")
        print("─" * 80)
        print(f"   💰 Başlangıç: $10,000 → Bitiş: ${r['balance']:,.2f}")
        print(f"   📈 Net Kar: ${r['profit']:+,.2f} ({r['roi']:+.2f}%)")
        print(f"   🛡️  Max Drawdown: {r['max_drawdown']:.2f}%")
        print(f"   📊 Toplam İşlem: {len(trades)}")
        print(f"   ✅ Kazanan: {len(winning)} ({len(winning)/len(trades)*100:.1f}%)")
        print(f"   ❌ Kaybeden: {len(losing)} ({len(losing)/len(trades)*100:.1f}%)")

        if winning:
            avg_win = np.mean([t['profit'] for t in winning])
            print(f"   💵 Ort. Kazanç: ${avg_win:.2f}")

        if losing:
            avg_loss = np.mean([t['profit'] for t in losing])
            print(f"   💸 Ort. Zarar: ${avg_loss:.2f}")

        # Profit Factor
        total_win = sum([t['profit'] for t in winning]) if winning else 0
        total_loss = abs(sum([t['profit'] for t in losing])) if losing else 1
        pf = total_win / total_loss if total_loss > 0 else float('inf')
        print(f"   ⚖️  Profit Factor: {pf:.2f}")

        # Exit reasons
        exit_reasons = {}
        for t in trades:
            reason = t['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

        print(f"\n   🎯 ÇIKIŞ SEBEPLERİ:")
        for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
            pct = (count / len(trades)) * 100
            print(f"      {reason:20} → {count:3} işlem ({pct:.1f}%)")

    # FINAL DEĞERLENDİRME
    print("\n" + "="*80)
    print("✅ FINAL DEĞERLENDİRME")
    print("="*80)

    # 2023 ve 2024 karşılaştır
    r2023 = results[0]
    r2024 = results[1]

    checks = []

    # 1. Her iki yıl da pozitif mi?
    if r2023['roi'] > 0 and r2024['roi'] > 0:
        checks.append("✅ Her iki yıl da pozitif (Tutarlı)")
    else:
        checks.append("❌ Tutarsızlık var")

    # 2. Drawdown < 5% mi?
    avg_dd = (r2023['max_drawdown'] + r2024['max_drawdown']) / 2
    if abs(avg_dd) < 5:
        checks.append(f"✅ Mükemmel drawdown kontrolü ({avg_dd:.2f}%)")
    else:
        checks.append(f"⚠️  Yüksek drawdown ({avg_dd:.2f}%)")

    # 3. Win rate > 50%?
    all_trades = r2023['trades'] + r2024['trades']
    winning_all = [t for t in all_trades if t['profit'] > 0]
    wr = len(winning_all) / len(all_trades) * 100
    if wr >= 60:
        checks.append(f"✅ Yüksek win rate ({wr:.1f}%)")
    elif wr >= 50:
        checks.append(f"✅ İyi win rate ({wr:.1f}%)")
    else:
        checks.append(f"⚠️  Düşük win rate ({wr:.1f}%)")

    # 4. ROI farkı < %10?
    roi_diff = abs(r2023['roi'] - r2024['roi'])
    if roi_diff < 5:
        checks.append(f"✅ Çok tutarlı ROI (fark: {roi_diff:.1f}%)")
    elif roi_diff < 10:
        checks.append(f"✅ Tutarlı ROI (fark: {roi_diff:.1f}%)")
    else:
        checks.append(f"⚠️  ROI değişken (fark: {roi_diff:.1f}%)")

    print("\n📋 KONTROL LİSTESİ:\n")
    for check in checks:
        print(f"   {check}")

    passed = sum(1 for c in checks if c.startswith("✅"))
    score = (passed / len(checks)) * 100

    print(f"\n{'='*80}")
    print(f"FINAL SKOR: {passed}/{len(checks)} ({score:.0f}%)")
    print(f"{'='*80}")

    if score >= 75:
        print("\n🎉 STRATEJİ GERÇEK TRADE İÇİN HAZIR!")
        print("\n📌 SONRAKİ ADIMLAR:")
        print("   1. Paper trading ile gerçek piyasada test et")
        print("   2. Küçük pozisyonlarla canlı test başlat")
        print("   3. 1-2 ay performansı izle")
        print("   4. Pozisyon boyutunu kademeli artır")
    elif score >= 50:
        print("\n⚠️  STRATEJİ İYİ AMA DİKKATLİ KULLAN")
        print("   → Paper trading ile daha fazla test önerilir")
    else:
        print("\n❌ STRATEJİ DAHA FAZLA OPTİMİZASYON GEREKTİRİYOR")

    print("\n" + "="*80)
    print("✅ Final test tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
