#!/usr/bin/env python3
"""
Test High Quality Strategy
===========================

Test the strict filtering strategy on 7-year data
Compare with baseline to see trade reduction vs ROI improvement
"""

import pandas as pd
import numpy as np
from datetime import datetime


def load_csv_data(csv_path):
    """Load CSV data"""
    print("Loading data...")
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
    return df


def resample_to_4h(df_15m):
    """Resample to 4h"""
    df_4h = df_15m.resample('4h').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    return df_4h.dropna()


def calculate_atr(df, period=14):
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


def backtest_high_quality(df_15m, df_4h):
    """Run HIGH QUALITY strategy backtest"""
    print("Running HIGH QUALITY backtest...")

    leverage = 10
    base_position_size = 0.05
    base_tp = 0.007
    base_sl = 0.0035
    commission = 0.0004

    # HIGH QUALITY THRESHOLDS
    MIN_FRACTAL_STRENGTH = 60  # Was 50
    MIN_FRACTAL_CONSISTENCY = 0.005  # New
    MIN_4H_TREND_STRENGTH = 0.02  # Price >2% above EMA
    MIN_4H_EMA_SLOPE = 0.0005  # EMA must be rising
    MIN_ADX = 25  # Only trending
    MIN_VOLUME_RATIO = 1.2  # Volume confirmation

    # Prep data
    df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()
    df_4h['ema_slope'] = df_4h['ema_50'].diff() / df_4h['ema_50']
    df_4h['trend_strength'] = np.where(
        df_4h['close'] > df_4h['ema_50'],
        (df_4h['close'] - df_4h['ema_50']) / df_4h['ema_50'],
        0
    )

    for col in ['close', 'ema_50', 'ema_slope', 'trend_strength']:
        df_15m[f'4h_{col}'] = df_15m.index.map(
            lambda dt: df_4h[df_4h.index <= dt][col].iloc[-1]
            if len(df_4h[df_4h.index <= dt]) > 0 else np.nan
        )

    df_15m['atr'] = calculate_atr(df_15m, 14)
    df_15m['adx'] = calculate_adx(df_15m, 14)
    df_15m['baseline_atr'] = df_15m['atr'].rolling(100, min_periods=1).mean()
    df_15m['volume_ma'] = df_15m['volume'].rolling(20).mean()
    df_15m['volume_ratio'] = df_15m['volume'] / df_15m['volume_ma']

    # Fractal detection with consistency
    df_15m['fractal_pattern'] = None
    df_15m['fractal_strength'] = 0
    df_15m['fractal_consistency'] = 0

    print("Detecting high-quality fractals...")
    for i in range(2, len(df_15m)):
        if i % 10000 == 0:
            print(f"  Progress: {i}/{len(df_15m)} ({i/len(df_15m)*100:.1f}%)")

        curr = df_15m.iloc[i]
        prev1 = df_15m.iloc[i-1]
        prev2 = df_15m.iloc[i-2]

        # Trending Up
        if (curr['close'] > prev1['close'] > prev2['close'] and
            curr['high'] > prev1['high'] > prev2['high']):
            body = abs(curr['close'] - curr['open'])
            range_val = curr['high'] - curr['low']
            if range_val > 0:
                strength = int((body / range_val) * 100)

                # Consistency
                close_consistency = min(
                    (curr['close'] - prev1['close']) / curr['close'],
                    (prev1['close'] - prev2['close']) / prev1['close']
                ) if curr['close'] > 0 and prev1['close'] > 0 else 0

                df_15m.iloc[i, df_15m.columns.get_loc('fractal_pattern')] = 'Trending Up'
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_strength')] = strength
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_consistency')] = close_consistency

        # Outside Bar
        elif (curr['high'] > prev1['high'] and
              curr['low'] < prev1['low'] and
              curr['close'] > curr['open']):
            body = abs(curr['close'] - curr['open'])
            range_val = curr['high'] - curr['low']
            if range_val > 0:
                strength = int((body / range_val) * 100)
                consistency = (body / range_val) if range_val > 0 else 0

                df_15m.iloc[i, df_15m.columns.get_loc('fractal_pattern')] = 'Outside Bar'
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_strength')] = strength
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_consistency')] = consistency

    df_15m.dropna(inplace=True)
    print("Fractals detected!")

    # Backtest
    print("\nRunning backtest...")
    balance = 10000
    peak_balance = 10000
    trades = []
    current_trade = None
    recent_trades = []
    filtered_count = 0  # Count how many trades were filtered out

    for idx, row in df_15m.iterrows():
        if balance > peak_balance:
            peak_balance = balance

        if current_trade is None:
            # Adaptive features
            vol_ratio = row['atr'] / row['baseline_atr'] if row['baseline_atr'] > 0 else 1.0
            adaptive_tp = base_tp * vol_ratio
            adaptive_sl = base_sl * vol_ratio
            adaptive_tp = np.clip(adaptive_tp, 0.004, 0.015)
            adaptive_sl = np.clip(adaptive_sl, 0.002, 0.008)

            adx = row['adx']
            if adx > 25:
                tp_multiplier = 1.2
                strength_adj = 0  # Keep strict
            elif adx < 20:
                tp_multiplier = 0.8
                strength_adj = +10
            else:
                tp_multiplier = 1.0
                strength_adj = +5

            adaptive_tp *= tp_multiplier
            min_strength = MIN_FRACTAL_STRENGTH + strength_adj

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

            # === HIGH QUALITY ENTRY CHECK ===

            # Basic checks (same as baseline)
            if (row['fractal_pattern'] not in ['Trending Up', 'Outside Bar'] or
                row['fractal_strength'] < min_strength or
                row['4h_close'] <= row['4h_ema_50']):
                continue

            # NEW FILTER 1: Fractal consistency
            if row['fractal_consistency'] < MIN_FRACTAL_CONSISTENCY:
                filtered_count += 1
                continue

            # NEW FILTER 2: Strong 4h trend (>2% above EMA)
            if row['4h_trend_strength'] < MIN_4H_TREND_STRENGTH:
                filtered_count += 1
                continue

            # NEW FILTER 3: 4h EMA rising
            if row['4h_ema_slope'] < MIN_4H_EMA_SLOPE:
                filtered_count += 1
                continue

            # NEW FILTER 4: High ADX (trending)
            if adx < MIN_ADX:
                filtered_count += 1
                continue

            # NEW FILTER 5: Volume confirmation
            if row['volume_ratio'] < MIN_VOLUME_RATIO:
                filtered_count += 1
                continue

            # ALL FILTERS PASSED - HIGH QUALITY TRADE!

            if dd >= -0.05:
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
                if current_price >= current_trade['entry_price'] * 1.005:
                    current_trade['trailing_active'] = True
                    current_trade['trailing_stop'] = current_price * 0.998

            if current_trade['trailing_active']:
                new_trailing = current_trade['highest_price'] * 0.998
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

                trades.append({'pnl': net_pnl, 'exit_type': exit_type})
                current_trade = None

    # Results
    roi = ((balance - 10000) / 10000) * 100
    trades_df = pd.DataFrame(trades)

    if len(trades_df) > 0:
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

        exit_counts = trades_df['exit_type'].value_counts().to_dict()
    else:
        win_rate = 0
        profit_factor = 0
        max_dd = 0
        exit_counts = {}

    return {
        'roi': roi,
        'final_balance': balance,
        'num_trades': len(trades_df),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_dd': max_dd,
        'exit_counts': exit_counts,
        'filtered_count': filtered_count,
    }


def main():
    print("="*80)
    print("HIGH QUALITY STRATEGY TEST - 7 YEARS")
    print("="*80)
    print()

    # Load data
    csv_path = '/home/voidstring/Desktop/jesse_real/btc_15m_data_2018_to_2025.csv'
    df_15m = load_csv_data(csv_path)
    df_4h = resample_to_4h(df_15m)

    print(f"Data: {df_15m.index[0]} to {df_15m.index[-1]}")
    print()

    # Test HIGH QUALITY strategy
    hq_result = backtest_high_quality(df_15m.copy(), df_4h.copy())

    # Results
    print("\n" + "="*80)
    print("RESULTS - HIGH QUALITY STRATEGY")
    print("="*80)
    print()
    print(f"ROI: {hq_result['roi']:.2f}%")
    print(f"Final Balance: ${hq_result['final_balance']:.2f}")
    print(f"Trades: {hq_result['num_trades']}")
    print(f"Trades Filtered Out: {hq_result['filtered_count']}")
    print(f"Win Rate: {hq_result['win_rate']:.1f}%")
    print(f"Profit Factor: {hq_result['profit_factor']:.2f}")
    print(f"Max Drawdown: {hq_result['max_dd']:.2f}%")
    print()

    if hq_result['exit_counts']:
        print("Exit Distribution:")
        for exit_type, count in hq_result['exit_counts'].items():
            pct = (count / hq_result['num_trades']) * 100
            print(f"  {exit_type}: {count} ({pct:.1f}%)")
    print()

    # Comparison with baseline
    baseline_roi = 714.50
    baseline_trades = 5814
    baseline_wr = 49.7
    baseline_dd = -3.18

    print("="*80)
    print("COMPARISON: Baseline vs High Quality")
    print("="*80)
    print()
    print(f"{'Metric':<25} {'Baseline':<15} {'High Quality':<15} {'Change':<15}")
    print("-"*80)

    hq_roi_str = f"{hq_result['roi']:.2f}%"
    roi_change = f"{hq_result['roi'] - baseline_roi:+.2f}%"
    print(f"{'ROI':<25} {baseline_roi:.2f}%{' '*7} {hq_roi_str:<15} {roi_change:<15}")

    hq_trades_str = f"{hq_result['num_trades']}"
    trade_reduction = ((baseline_trades - hq_result['num_trades']) / baseline_trades) * 100
    trades_change = f"-{trade_reduction:.1f}%"
    print(f"{'Trades':<25} {baseline_trades}{' '*10} {hq_trades_str:<15} {trades_change:<15}")

    hq_wr_str = f"{hq_result['win_rate']:.1f}%"
    wr_change = f"{hq_result['win_rate'] - baseline_wr:+.1f}%"
    print(f"{'Win Rate':<25} {baseline_wr:.1f}%{' '*9} {hq_wr_str:<15} {wr_change:<15}")

    hq_dd_str = f"{hq_result['max_dd']:.2f}%"
    dd_change = f"{hq_result['max_dd'] - baseline_dd:+.2f}%"
    print(f"{'Max DD':<25} {baseline_dd:.2f}%{' '*9} {hq_dd_str:<15} {dd_change:<15}")

    # ROI per trade
    baseline_roi_per_trade = baseline_roi / baseline_trades
    hq_roi_per_trade = hq_result['roi'] / hq_result['num_trades'] if hq_result['num_trades'] > 0 else 0
    roi_per_trade_change = hq_roi_per_trade / baseline_roi_per_trade if baseline_roi_per_trade > 0 else 0

    print()
    print(f"ROI per trade:")
    print(f"  Baseline: {baseline_roi_per_trade:.4f}%")
    print(f"  High Quality: {hq_roi_per_trade:.4f}%")
    print(f"  Improvement: {roi_per_trade_change:.2f}x")
    print()

    # Assessment
    print("="*80)
    print("ASSESSMENT")
    print("="*80)
    print()

    if hq_result['roi'] > baseline_roi * 0.9 and trade_reduction > 50:
        print(f"✅ SUCCESS!")
        print(f"   - {trade_reduction:.0f}% fewer trades")
        print(f"   - {hq_result['win_rate'] - baseline_wr:+.1f}% better win rate")
        print(f"   - {roi_per_trade_change:.1f}x better ROI per trade")
        if hq_result['roi'] > baseline_roi:
            print(f"   - {hq_result['roi'] - baseline_roi:.1f}% HIGHER total ROI!")
    elif hq_result['roi'] > baseline_roi:
        print(f"✅ BETTER ROI!")
        print(f"   - {hq_result['roi'] - baseline_roi:.1f}% improvement")
    else:
        print(f"⚠️  Trade quality vs quantity tradeoff")
        print(f"   - Fewer trades but similar/lower ROI")

    print()
    print("="*80)


if __name__ == '__main__':
    main()
