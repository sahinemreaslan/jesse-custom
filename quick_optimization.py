#!/usr/bin/env python3
"""
Quick Hyperparameter Optimization
=================================

Fast optimization with:
- Small parameter grid (50 combinations)
- Short test period (2024 only - 10 months)
- Quick validation
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime


def load_csv_data(csv_path, start_date, end_date):
    """Load and filter CSV data"""
    print(f"Loading {start_date} to {end_date}...")
    df = pd.read_csv(csv_path)
    df['Open time'] = pd.to_datetime(df['Open time'].str.strip())
    df = df.rename(columns={
        'Open time': 'timestamp',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    })
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df = df.drop_duplicates(subset=['timestamp'])
    df = df.sort_values('timestamp')
    df.set_index('timestamp', inplace=True)
    df = df.ffill().dropna()

    # Filter dates
    df = df[(df.index >= start_date) & (df.index <= end_date)]
    return df


def resample_to_4h(df_15m):
    """Resample 15m to 4h"""
    df_4h = df_15m.resample('4h').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    return df_4h.dropna()


def calculate_atr(df, period=14):
    """Calculate ATR"""
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    tr = np.zeros(len(df))
    for i in range(1, len(df)):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr[i] = max(hl, hc, lc)
    atr = pd.Series(tr).ewm(span=period, adjust=False).mean()
    return atr.values


def calculate_adx(df, period=14):
    """Calculate ADX"""
    high = df['high'].values
    low = df['low'].values
    plus_dm = np.zeros(len(df))
    minus_dm = np.zeros(len(df))
    for i in range(1, len(df)):
        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
    atr = calculate_atr(df, period)
    plus_di = 100 * pd.Series(plus_dm).ewm(span=period, adjust=False).mean() / (atr + 1e-10)
    minus_di = 100 * pd.Series(minus_dm).ewm(span=period, adjust=False).mean() / (atr + 1e-10)
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(span=period, adjust=False).mean()
    return adx.values


def backtest_with_params(df_15m, df_4h, params):
    """Run backtest with specific parameters"""

    leverage = 10
    base_position_size = params['base_position_size']
    base_tp = params['base_tp']
    base_sl = params['base_sl']
    min_fractal_strength = params['min_fractal_strength']
    trailing_activation = params['trailing_activation']
    trailing_distance = params['trailing_distance']
    atr_lookback = params['atr_lookback']
    commission = 0.0004

    # Prep data
    df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()

    for col in ['close', 'ema_50']:
        df_15m[f'4h_{col}'] = df_15m.index.map(
            lambda dt: df_4h[df_4h.index <= dt][col].iloc[-1]
            if len(df_4h[df_4h.index <= dt]) > 0 else np.nan
        )

    df_15m['atr'] = calculate_atr(df_15m, 14)
    df_15m['adx'] = calculate_adx(df_15m, 14)
    df_15m['baseline_atr'] = df_15m['atr'].rolling(atr_lookback, min_periods=1).mean()

    # Fractal detection
    df_15m['fractal_pattern'] = None
    df_15m['fractal_strength'] = 0

    for i in range(2, len(df_15m)):
        curr = df_15m.iloc[i]
        prev1 = df_15m.iloc[i-1]
        prev2 = df_15m.iloc[i-2]

        if (curr['close'] > prev1['close'] > prev2['close'] and
            curr['high'] > prev1['high'] > prev2['high']):
            body = abs(curr['close'] - curr['open'])
            range_val = curr['high'] - curr['low']
            if range_val > 0:
                strength = int((body / range_val) * 100)
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_pattern')] = 'Trending Up'
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_strength')] = strength

        elif (curr['high'] > prev1['high'] and
              curr['low'] < prev1['low'] and
              curr['close'] > curr['open']):
            body = abs(curr['close'] - curr['open'])
            range_val = curr['high'] - curr['low']
            if range_val > 0:
                strength = int((body / range_val) * 100)
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_pattern')] = 'Outside Bar'
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_strength')] = strength

    df_15m.dropna(inplace=True)

    # Backtest
    balance = 10000
    peak_balance = 10000
    trades = []
    current_trade = None
    recent_trades = []

    for idx, row in df_15m.iterrows():
        if balance > peak_balance:
            peak_balance = balance

        if current_trade is None:
            vol_ratio = row['atr'] / row['baseline_atr'] if row['baseline_atr'] > 0 else 1.0
            adaptive_tp = base_tp * vol_ratio
            adaptive_sl = base_sl * vol_ratio
            adaptive_tp = np.clip(adaptive_tp, 0.004, 0.015)
            adaptive_sl = np.clip(adaptive_sl, 0.002, 0.008)

            adx = row['adx']
            if adx > 25:
                tp_multiplier = 1.2
                strength_adj = -5
            elif adx < 20:
                tp_multiplier = 0.8
                strength_adj = +10
            else:
                tp_multiplier = 1.0
                strength_adj = 0

            adaptive_tp *= tp_multiplier
            min_strength = min_fractal_strength + strength_adj

            dd = (balance - peak_balance) / peak_balance if peak_balance > 0 else 0

            if dd >= 0:
                dd_multiplier = 1.0
            elif dd > -0.01:
                dd_multiplier = 1.0
            elif dd > -0.02:
                dd_multiplier = 0.9
            elif dd > -0.03:
                dd_multiplier = 0.7
            elif dd > -0.04:
                dd_multiplier = 0.5
            elif dd > -0.05:
                dd_multiplier = 0.3
            else:
                dd_multiplier = 0

            position_size = base_position_size * dd_multiplier

            if position_size == 0:
                continue

            if len(recent_trades) >= 10:
                win_rate = sum([1 for t in recent_trades[-20:] if t > 0]) / len(recent_trades[-20:])
                if win_rate > 0.6:
                    position_size *= 1.1
                elif win_rate < 0.4:
                    position_size *= 0.9

            position_size = np.clip(position_size, 0.01, 0.08)

            if (dd >= -0.05 and
                row['fractal_pattern'] in ['Trending Up', 'Outside Bar'] and
                row['fractal_strength'] >= min_strength and
                row['4h_close'] > row['4h_ema_50']):

                position_value = balance * position_size * leverage
                entry_commission = position_value * commission

                current_trade = {
                    'entry_price': row['close'],
                    'position_value': position_value,
                    'collateral': balance * position_size,
                    'tp_price': row['close'] * (1 + adaptive_tp),
                    'sl_price': row['close'] * (1 - adaptive_sl),
                    'highest_price': row['close'],
                    'trailing_active': False,
                    'trailing_stop': None,
                    'entry_commission': entry_commission,
                }

        else:
            current_price = row['close']
            high_price = row['high']
            low_price = row['low']

            if high_price > current_trade['highest_price']:
                current_trade['highest_price'] = high_price

            if not current_trade['trailing_active']:
                if current_price >= current_trade['entry_price'] * (1 + trailing_activation):
                    current_trade['trailing_active'] = True
                    current_trade['trailing_stop'] = current_price * (1 - trailing_distance)

            if current_trade['trailing_active']:
                new_trailing = current_trade['highest_price'] * (1 - trailing_distance)
                if new_trailing > current_trade['trailing_stop']:
                    current_trade['trailing_stop'] = new_trailing

            exit_type = None
            exit_price = None

            if low_price <= current_trade['sl_price']:
                exit_type = 'SL'
                exit_price = current_trade['sl_price']
            elif high_price >= current_trade['tp_price']:
                exit_type = 'TP'
                exit_price = current_trade['tp_price']
            elif current_trade['trailing_active'] and low_price <= current_trade['trailing_stop']:
                exit_type = 'Trailing'
                exit_price = current_trade['trailing_stop']

            if exit_type:
                exit_commission = current_trade['position_value'] * commission
                price_change = (exit_price / current_trade['entry_price']) - 1
                leveraged_pnl = price_change * leverage
                gross_pnl = current_trade['collateral'] * leveraged_pnl
                net_pnl = gross_pnl - current_trade['entry_commission'] - exit_commission

                balance += net_pnl
                recent_trades.append(net_pnl)
                if len(recent_trades) > 20:
                    recent_trades.pop(0)

                trades.append({'pnl': net_pnl})
                current_trade = None

    # Calculate metrics
    if len(trades) == 0:
        return None

    trades_df = pd.DataFrame(trades)
    roi = ((balance - 10000) / 10000) * 100

    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]
    win_rate = len(wins) / len(trades_df) * 100

    total_profit = wins['pnl'].sum() if len(wins) > 0 else 0
    total_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1
    profit_factor = total_profit / total_loss

    trades_df['balance'] = 10000 + trades_df['pnl'].cumsum()
    trades_df['peak'] = trades_df['balance'].expanding().max()
    trades_df['dd'] = (trades_df['balance'] - trades_df['peak']) / trades_df['peak'] * 100
    max_dd = trades_df['dd'].min()

    # Sharpe-like ratio
    returns = trades_df['pnl'] / 10000
    sharpe = returns.mean() / returns.std() if returns.std() > 0 else 0

    # Composite score
    score = roi * (1 - abs(max_dd)/100) * np.sqrt(profit_factor) * (1 + sharpe)

    return {
        'roi': roi,
        'final_balance': balance,
        'num_trades': len(trades_df),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_dd': max_dd,
        'sharpe': sharpe,
        'score': score,
    }


def main():
    print("="*80)
    print("QUICK HYPERPARAMETER OPTIMIZATION")
    print("="*80)
    print()

    # Load data (2024 only for speed)
    csv_path = '/home/voidstring/Desktop/jesse_real/btc_15m_data_2018_to_2025.csv'

    print("Loading 2024 data for training...")
    df_15m_train = load_csv_data(csv_path, '2024-01-01', '2024-08-31')
    df_4h_train = resample_to_4h(df_15m_train)
    print(f"Train: {len(df_15m_train)} candles (8 months)")

    print("Loading Sep-Oct 2024 for validation...")
    df_15m_val = load_csv_data(csv_path, '2024-09-01', '2024-10-31')
    df_4h_val = resample_to_4h(df_15m_val)
    print(f"Val: {len(df_15m_val)} candles (2 months)")
    print()

    # Define small parameter grid
    baseline_params = {
        'base_position_size': 0.05,
        'base_tp': 0.007,
        'base_sl': 0.0035,
        'min_fractal_strength': 50,
        'trailing_activation': 0.005,
        'trailing_distance': 0.002,
        'atr_lookback': 100,
    }

    # Create grid
    param_grid = [baseline_params]  # Start with baseline

    # Vary key parameters (focused search)
    for pos_size in [0.04, 0.05, 0.06]:
        for tp in [0.006, 0.007, 0.008]:
            for sl in [0.003, 0.0035, 0.004]:
                for strength in [45, 50, 55]:
                    if not (pos_size == 0.05 and tp == 0.007 and sl == 0.0035 and strength == 50):
                        param_grid.append({
                            'base_position_size': pos_size,
                            'base_tp': tp,
                            'base_sl': sl,
                            'min_fractal_strength': strength,
                            'trailing_activation': 0.005,  # Fixed
                            'trailing_distance': 0.002,    # Fixed
                            'atr_lookback': 100,           # Fixed
                        })

    print(f"Grid size: {len(param_grid)} combinations")
    print()

    # Training
    print("="*80)
    print("PHASE 1: Training (Jan-Aug 2024)")
    print("="*80)
    print()

    train_results = []

    for i, params in enumerate(param_grid):
        if i % 10 == 0:
            print(f"Progress: {i}/{len(param_grid)} ({i/len(param_grid)*100:.0f}%)")

        result = backtest_with_params(df_15m_train.copy(), df_4h_train.copy(), params)

        if result:
            train_results.append({
                'params': params,
                'metrics': result
            })

    # Sort by score
    train_results = sorted(train_results, key=lambda x: x['metrics']['score'], reverse=True)

    print(f"\n✅ Completed {len(train_results)} combinations")
    print()

    # Top 10
    print("="*80)
    print("TOP 10 PARAMETER SETS (Training)")
    print("="*80)
    print()

    for i, res in enumerate(train_results[:10]):
        print(f"#{i+1} | Score: {res['metrics']['score']:.1f}")
        print(f"     ROI: {res['metrics']['roi']:.2f}% | Trades: {res['metrics']['num_trades']}")
        print(f"     WR: {res['metrics']['win_rate']:.1f}% | PF: {res['metrics']['profit_factor']:.2f}")
        print(f"     Max DD: {res['metrics']['max_dd']:.2f}%")
        print(f"     Params: pos={res['params']['base_position_size']}, tp={res['params']['base_tp']}, sl={res['params']['base_sl']}, str={res['params']['min_fractal_strength']}")
        print()

    # Validation
    print("="*80)
    print("PHASE 2: Validation (Sep-Oct 2024)")
    print("="*80)
    print()

    validation_results = []

    for i, res in enumerate(train_results[:10]):
        print(f"Testing #{i+1}...")
        val_result = backtest_with_params(df_15m_val.copy(), df_4h_val.copy(), res['params'])

        if val_result:
            print(f"  Val ROI: {val_result['roi']:.2f}% | Trades: {val_result['num_trades']} | WR: {val_result['win_rate']:.1f}%")

            validation_results.append({
                'rank': i+1,
                'params': res['params'],
                'train_metrics': res['metrics'],
                'val_metrics': val_result
            })

    print()

    # Best overall
    print("="*80)
    print("BEST PARAMETERS")
    print("="*80)
    print()

    best = max(validation_results, key=lambda x: x['train_metrics']['score'] + x['val_metrics']['score'])

    print(f"Best Configuration:")
    print(f"  Training ROI: {best['train_metrics']['roi']:.2f}%")
    print(f"  Validation ROI: {best['val_metrics']['roi']:.2f}%")
    print(f"  Combined Score: {best['train_metrics']['score'] + best['val_metrics']['score']:.1f}")
    print()
    print(f"Parameters:")
    for key, val in best['params'].items():
        print(f"  {key}: {val}")
    print()

    # Compare with baseline
    baseline_result = validation_results[0]

    print("="*80)
    print("COMPARISON: Baseline vs Optimized")
    print("="*80)
    print()
    print(f"{'Metric':<20} {'Baseline':<15} {'Optimized':<15} {'Improvement':<10}")
    print("-"*80)

    baseline_roi = baseline_result['val_metrics']['roi']
    optimized_roi = best['val_metrics']['roi']
    print(f"{'Validation ROI':<20} {baseline_roi:+.2f}%{' '*8} {optimized_roi:+.2f}%{' '*8} {optimized_roi-baseline_roi:+.2f}%")

    baseline_dd = baseline_result['val_metrics']['max_dd']
    optimized_dd = best['val_metrics']['max_dd']
    print(f"{'Max DD':<20} {baseline_dd:.2f}%{' '*9} {optimized_dd:.2f}%{' '*9} {optimized_dd-baseline_dd:+.2f}%")

    baseline_wr = baseline_result['val_metrics']['win_rate']
    optimized_wr = best['val_metrics']['win_rate']
    print(f"{'Win Rate':<20} {baseline_wr:.1f}%{' '*10} {optimized_wr:.1f}%{' '*10} {optimized_wr-baseline_wr:+.1f}%")

    print()

    # Save results
    output = {
        'best_params': best['params'],
        'best_metrics': {
            'train': best['train_metrics'],
            'validation': best['val_metrics'],
        },
        'baseline_metrics': {
            'train': baseline_result['train_metrics'],
            'validation': baseline_result['val_metrics'],
        },
        'top_10': validation_results,
        'timestamp': datetime.now().isoformat(),
    }

    with open('quick_optimization_results.json', 'w') as f:
        json.dump(output, f, indent=2)

    print("✅ Results saved to quick_optimization_results.json")
    print()
    print("="*80)

    # Recommendation
    improvement = optimized_roi - baseline_roi
    if improvement > 5:
        print("🚀 RECOMMENDATION: Use optimized parameters!")
        print(f"   {improvement:.1f}% better ROI on validation set")
    elif improvement > 0:
        print("✅ RECOMMENDATION: Optimized parameters slightly better")
        print(f"   {improvement:.1f}% improvement, consider using optimized")
    else:
        print("⚠️  RECOMMENDATION: Stick with baseline")
        print(f"   Optimization didn't improve results significantly")

    print()
    print("="*80)


if __name__ == '__main__':
    main()
