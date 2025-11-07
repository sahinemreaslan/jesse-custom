"""
PARAMETER OPTİMİZATÖR - Grid Search ile En İyi Parametreleri Bul
═══════════════════════════════════════════════════════════
Amaç: Trailing Stop Master ve Momentum Guardian için
      en iyi parameter kombinasyonlarını bul

Test Edilecek Parametreler:
  - TP (Take Profit): %15, %20, %25, %30
  - SL (Stop Loss): %6, %7, %8, %9
  - Trailing Activation: %4, %5, %6, %7
  - Trailing Distance: %2, %2.5, %3, %3.5
  - Min Strength: 30, 35, 40, 45
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from itertools import product
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from advanced_trade_manager import TradeManager


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
                    trades.append({'profit': profit})
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
        'roi': ((balance - 10000) / 10000) * 100,
        'max_drawdown': max_drawdown
    }


def optimize_strategy(strategy_name, base_config, param_grid):
    """Stratejiyi optimize et"""

    print(f"\n{'='*80}")
    print(f"{strategy_name} - PARAMETER OPTİMİZASYONU")
    print(f"{'='*80}")

    # 2023 verisini yükle (training data)
    print(f"\n📊 2023 verisi yükleniyor (training)...")
    df_train = load_data_range(1672531200000, 1704067199000)

    # 2024 verisini yükle (validation data)
    print(f"📊 2024 verisi yükleniyor (validation)...")
    df_valid = load_data_range(1704067200000, 1735689599000)

    # Grid search
    param_combinations = list(product(*param_grid.values()))
    param_names = list(param_grid.keys())

    print(f"\n🔍 {len(param_combinations)} farklı kombinasyon test edilecek...")
    print(f"⏳ Bu birkaç dakika sürebilir...\n")

    results = []

    for i, params in enumerate(param_combinations, 1):
        if i % 10 == 0:
            print(f"   [{i}/{len(param_combinations)}] test edildi...")

        # Config oluştur
        config = base_config.copy()

        # Parametreleri uygula
        for param_name, param_value in zip(param_names, params):
            if param_name == 'min_strength':
                config['min_strength'] = param_value
            elif param_name == 'tp_percent':
                config['tp_percent'] = param_value / 100
            elif param_name == 'sl_percent':
                config['sl_percent'] = param_value / 100
            elif param_name == 'trailing_activation':
                config['trade_management']['trailing_stop_activation'] = param_value
            elif param_name == 'trailing_distance':
                config['trade_management']['trailing_stop_distance'] = param_value

        # Training test
        result_train = run_backtest(df_train, config)
        if result_train is None or len(result_train['trades']) < 5:
            continue

        # Validation test
        result_valid = run_backtest(df_valid, config)
        if result_valid is None or len(result_valid['trades']) < 5:
            continue

        # Skorlama: Her iki yıl da pozitif + düşük drawdown
        score = 0

        # Her iki yıl da pozitif (60 puan)
        if result_train['roi'] > 0 and result_valid['roi'] > 0:
            score += 60

        # Ortalama ROI (20 puan - max 50% ROI = 20 puan)
        avg_roi = (result_train['roi'] + result_valid['roi']) / 2
        score += min(avg_roi * 0.4, 20)

        # Düşük drawdown (20 puan - max drawdown -2% = 20 puan)
        avg_dd = (result_train['max_drawdown'] + result_valid['max_drawdown']) / 2
        dd_score = max(0, 20 + avg_dd * 10)  # Her %1 DD için -10 puan
        score += dd_score

        results.append({
            'params': dict(zip(param_names, params)),
            'train_roi': result_train['roi'],
            'valid_roi': result_valid['roi'],
            'train_dd': result_train['max_drawdown'],
            'valid_dd': result_valid['max_drawdown'],
            'train_trades': len(result_train['trades']),
            'valid_trades': len(result_valid['trades']),
            'score': score
        })

    # En iyi 10 sonuç
    results_sorted = sorted(results, key=lambda x: x['score'], reverse=True)[:10]

    print(f"\n{'='*80}")
    print(f"EN İYİ 10 PARAMETER KOMBİNASYONU")
    print(f"{'='*80}\n")

    for i, r in enumerate(results_sorted, 1):
        print(f"{i}. SKOR: {r['score']:.1f}/100")
        print(f"   Parametreler:")
        for param, value in r['params'].items():
            print(f"      {param:20} = {value}")
        print(f"   Training  : ROI {r['train_roi']:+6.2f}% | DD {r['train_dd']:6.2f}% | {r['train_trades']} trades")
        print(f"   Validation: ROI {r['valid_roi']:+6.2f}% | DD {r['valid_dd']:6.2f}% | {r['valid_trades']} trades")
        print()

    return results_sorted[0] if results_sorted else None


def main():
    """Ana optimizasyon fonksiyonu"""
    print("="*80)
    print("PARAMETER OPTİMİZATÖR - Grid Search")
    print("="*80)
    print("\n🎯 Amaç: En iyi parameter kombinasyonlarını bul")
    print("📊 Method: 2023 training, 2024 validation")
    print("="*80)

    # ═══════════════════════════════════════════════════════════
    # TRAILING STOP MASTER OPTİMİZASYONU
    # ═══════════════════════════════════════════════════════════

    tsm_base = {
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

    tsm_param_grid = {
        'min_strength': [30, 35, 40],
        'tp_percent': [20, 25, 30],
        'sl_percent': [6, 7, 8],
        'trailing_activation': [4, 5, 6],
        'trailing_distance': [2.5, 3.0, 3.5]
    }

    best_tsm = optimize_strategy("TRAILING STOP MASTER", tsm_base, tsm_param_grid)

    # ═══════════════════════════════════════════════════════════
    # MOMENTUM GUARDIAN OPTİMİZASYONU
    # ═══════════════════════════════════════════════════════════

    mg_base = {
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
    }

    mg_param_grid = {
        'min_strength': [35, 40, 45],
        'tp_percent': [18, 20, 22],
        'sl_percent': [6, 7, 8],
        'trailing_activation': [6, 7, 8],
        'trailing_distance': [2.0, 2.5, 3.0]
    }

    best_mg = optimize_strategy("MOMENTUM GUARDIAN", mg_base, mg_param_grid)

    # ═══════════════════════════════════════════════════════════
    # FINAL KARŞILAŞTIRMA
    # ═══════════════════════════════════════════════════════════

    print("\n" + "="*80)
    print("🏆 FINAL KARŞILAŞTIRMA")
    print("="*80)

    if best_tsm and best_mg:
        print(f"\n📊 TRAILING STOP MASTER (Optimize):")
        print(f"   Skor: {best_tsm['score']:.1f}/100")
        print(f"   2024 ROI: {best_tsm['valid_roi']:+.2f}%")
        print(f"   2024 DD: {best_tsm['valid_dd']:.2f}%")

        print(f"\n📊 MOMENTUM GUARDIAN (Optimize):")
        print(f"   Skor: {best_mg['score']:.1f}/100")
        print(f"   2024 ROI: {best_mg['valid_roi']:+.2f}%")
        print(f"   2024 DD: {best_mg['valid_dd']:.2f}%")

        if best_tsm['score'] > best_mg['score']:
            print(f"\n✅ KAZANAN: TRAILING STOP MASTER")
        elif best_mg['score'] > best_tsm['score']:
            print(f"\n✅ KAZANAN: MOMENTUM GUARDIAN")
        else:
            print(f"\n🤝 BERABERLİK - Her ikisi de mükemmel!")

    print("\n" + "="*80)
    print("✅ Optimizasyon tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
