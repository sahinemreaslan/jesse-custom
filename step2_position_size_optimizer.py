"""
ADIM 2: POZİSYON BOYUTU OPTİMİZASYONU
═══════════════════════════════════════════════════════════
Amaç: En iyi pozisyon boyutunu bul
       - %5, %10, %15, %20, %25 pozisyon boyutlarını test et
       - Compound etkisini kontrol et
       - Risk/Getiri dengesini analiz et

Neden: %20 pozisyon çok agresif olabilir. Optimal boyutu bulmalıyız.
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from advanced_trade_manager import TradeManager


def load_data():
    """2023 yılı verilerini yükle"""
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


def run_backtest_with_position_size(df, position_size_pct):
    """Belirli pozisyon boyutu ile backtest çalıştır"""
    config = {
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'min_strength': 30,
        'position_size': position_size_pct,  # DEĞIŞKEN
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
        'max_drawdown': max_drawdown,
        'balance_history': balance_history
    }


def main():
    """Ana test fonksiyonu"""
    print("="*80)
    print("ADIM 2: POZİSYON BOYUTU OPTİMİZASYONU")
    print("="*80)
    print("\nTest edilen pozisyon boyutları:")
    print("  - %5  (Çok Muhafazakar)")
    print("  - %10 (Muhafazakar)")
    print("  - %15 (Dengeli)")
    print("  - %20 (Agresif) - Mevcut")
    print("  - %25 (Çok Agresif)")
    print("\n" + "="*80)

    # Veri yükle
    print("\n📊 Veri yükleniyor...")
    df = load_data()
    print(f"✅ {len(df)} mum yüklendi (2023 yılı)")

    # Test edilecek pozisyon boyutları
    position_sizes = [0.05, 0.10, 0.15, 0.20, 0.25]
    results = []

    print("\n⏳ Optimizasyon başlıyor...\n")

    for pos_size in position_sizes:
        print(f"   Test: %{int(pos_size*100)} pozisyon boyutu...")
        result = run_backtest_with_position_size(df, pos_size)
        result['position_size'] = pos_size
        results.append(result)

    # SONUÇLARI GÖSTER
    print("\n" + "="*80)
    print("OPTİMİZASYON SONUÇLARI")
    print("="*80)

    print(f"\n{'Pozisyon':<12} {'Getiri':<15} {'Max DD':<15} {'İşlem':<10} {'Risk/Reward'}")
    print("─" * 80)

    for result in results:
        pos_pct = int(result['position_size'] * 100)
        num_trades = len(result['trades'])

        # Risk/Reward skoru (Getiri / Drawdown)
        risk_reward = abs(result['roi'] / result['max_drawdown']) if result['max_drawdown'] != 0 else 0

        marker = "  ⭐" if pos_pct == 20 else ""  # Mevcut strateji

        print(f"%{pos_pct:<10} {result['roi']:>6.2f}%{'':<8} "
              f"{result['max_drawdown']:>6.2f}%{'':<8} "
              f"{num_trades:<10} {risk_reward:>6.2f}{marker}")

    # EN İYİ SEÇİM
    print("\n" + "="*80)
    print("📊 DETAYLI ANALİZ")
    print("="*80)

    # En yüksek getiri
    best_roi = max(results, key=lambda x: x['roi'])
    print(f"\n🏆 En Yüksek Getiri:")
    print(f"   %{int(best_roi['position_size']*100)} pozisyon → {best_roi['roi']:+.2f}% getiri")

    # En düşük drawdown
    best_dd = max(results, key=lambda x: x['max_drawdown'])  # En az negatif
    print(f"\n🛡️  En Düşük Drawdown:")
    print(f"   %{int(best_dd['position_size']*100)} pozisyon → {best_dd['max_drawdown']:.2f}% drawdown")

    # En iyi Risk/Reward
    best_rr = max(results, key=lambda x: abs(x['roi'] / x['max_drawdown']) if x['max_drawdown'] != 0 else 0)
    rr_score = abs(best_rr['roi'] / best_rr['max_drawdown']) if best_rr['max_drawdown'] != 0 else 0
    print(f"\n⚖️  En İyi Risk/Reward:")
    print(f"   %{int(best_rr['position_size']*100)} pozisyon → {rr_score:.2f} R/R oranı")

    # ÖNERİ
    print("\n" + "="*80)
    print("💡 ÖNERİ")
    print("="*80)

    print(f"\nMevcut Strateji: %20 pozisyon")
    print(f"  Getiri: {results[3]['roi']:+.2f}%")
    print(f"  Drawdown: {results[3]['max_drawdown']:.2f}%")

    if best_rr['position_size'] != 0.20:
        print(f"\n✅ ÖNERİLEN: %{int(best_rr['position_size']*100)} pozisyon")
        print(f"  Getiri: {best_rr['roi']:+.2f}%")
        print(f"  Drawdown: {best_rr['max_drawdown']:.2f}%")
        print(f"  Avantaj: Daha iyi risk/reward dengesi")
    else:
        print(f"\n✅ MEVCUT AYAR OPTIMAL!")

    print("\n" + "="*80)
    print("✅ Adım 2 tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
