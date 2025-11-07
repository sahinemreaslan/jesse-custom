#!/usr/bin/env python3
"""
Test OUTSIDE BAR ONLY Strategy
================================

Simplest improvement: Only trade Outside Bars
Analysis showed: 51% WR vs 49.4% for Trending Up
Avg PnL: $15.05 vs $11.54

Expected: ~20% fewer trades, similar or better ROI
"""

import pandas as pd
import numpy as np


def load_csv_data(csv_path):
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


def backtest_outside_bar(df_15m, df_4h):
    """OUTSIDE BAR ONLY - simple but effective"""
    print("Running OUTSIDE BAR ONLY backtest...")

    leverage = 10
    base_position_size = 0.05
    base_tp = 0.007
    base_sl = 0.0035
    commission = 0.0004

    # ONLY CHANGE: Accept Outside Bar only!
    # Everything else same as baseline

    # Prep data
    df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()

    for col in ['close', 'ema_50']:
        df_15m[f'4h_{col}'] = df_15m.index.map(
            lambda dt: df_4h[df_4h.index <= dt][col].iloc[-1]
            if len(df_4h[df_4h.index <= dt]) > 0 else np.nan
        )

    df_15m['atr'] = calculate_atr(df_15m, 14)
    df_15m['adx'] = calculate_adx(df_15m, 14)
    df_15m['baseline_atr'] = df_15m['atr'].rolling(100, min_periods=1).mean()

    # Fractal detection
    df_15m['fractal_pattern'] = None
    df_15m['fractal_strength'] = 0

    print("Detecting fractals...")
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
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_pattern')] = 'Trending Up'
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_strength')] = strength

        # Outside Bar (THE ONLY ONE WE WANT!)
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
    print("Fractals detected!")

    # Backtest (EXACT SAME AS BASELINE except pattern filter)
    print("\nRunning backtest...")
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
            min_strength = 50 + strength_adj

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

            # === ONLY CHANGE: Outside Bar ONLY ===
            if (dd >= -0.05 and
                row['fractal_pattern'] == 'Outside Bar' and  # <-- ONLY THIS
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
    }


def main():
    print("="*80)
    print("OUTSIDE BAR ONLY STRATEGY TEST - 7 YEARS")
    print("="*80)
    print()

    # Load data
    csv_path = '/home/voidstring/Desktop/jesse_real/btc_15m_data_2018_to_2025.csv'
    df_15m = load_csv_data(csv_path)
    df_4h = resample_to_4h(df_15m)

    print(f"Data: {df_15m.index[0]} to {df_15m.index[-1]}")
    print()

    # Test Outside Bar Only
    result = backtest_outside_bar(df_15m.copy(), df_4h.copy())

    # Results
    print("\n" + "="*80)
    print("RESULTS - OUTSIDE BAR ONLY")
    print("="*80)
    print()
    print(f"ROI: {result['roi']:.2f}%")
    print(f"Final Balance: ${result['final_balance']:.2f}")
    print(f"Trades: {result['num_trades']}")
    print(f"Win Rate: {result['win_rate']:.1f}%")
    print(f"Profit Factor: {result['profit_factor']:.2f}")
    print(f"Max Drawdown: {result['max_dd']:.2f}%")
    print()

    if result['exit_counts']:
        print("Exit Distribution:")
        for exit_type, count in result['exit_counts'].items():
            pct = (count / result['num_trades']) * 100
            print(f"  {exit_type}: {count} ({pct:.1f}%)")
    print()

    # Comparison
    baseline_roi = 714.50
    baseline_trades = 5814
    baseline_wr = 49.7

    print("="*80)
    print("COMPARISON: Baseline vs Outside Bar Only")
    print("="*80)
    print()
    print(f"{'Metric':<25} {'Baseline (Both)':<20} {'Outside Bar Only':<20} {'Change':<15}")
    print("-"*80)

    result_roi_str = f"{result['roi']:.2f}%"
    roi_change = f"{result['roi'] - baseline_roi:+.2f}%"
    print(f"{'ROI':<25} {baseline_roi:.2f}%{' '*12} {result_roi_str:<20} {roi_change:<15}")

    result_trades_str = f"{result['num_trades']}"
    trade_reduction = ((baseline_trades - result['num_trades']) / baseline_trades) * 100
    trades_change = f"-{trade_reduction:.0f}%"
    print(f"{'Trades':<25} {baseline_trades}{' '*15} {result_trades_str:<20} {trades_change:<15}")

    result_wr_str = f"{result['win_rate']:.1f}%"
    wr_change = f"{result['win_rate'] - baseline_wr:+.1f}%"
    print(f"{'Win Rate':<25} {baseline_wr:.1f}%{' '*14} {result_wr_str:<20} {wr_change:<15}")

    result_dd_str = f"{result['max_dd']:.2f}%"
    dd_change = f"{result['max_dd'] + 3.18:+.2f}%"
    print(f"{'Max DD':<25} {'-3.18%':<20} {result_dd_str:<20} {dd_change:<15}")

    # ROI per trade
    baseline_roi_per_trade = baseline_roi / baseline_trades
    result_roi_per_trade = result['roi'] / result['num_trades'] if result['num_trades'] > 0 else 0

    print()
    print(f"ROI per trade:")
    print(f"  Baseline: {baseline_roi_per_trade:.4f}%")
    print(f"  Outside Bar: {result_roi_per_trade:.4f}%")
    if result_roi_per_trade > baseline_roi_per_trade:
        improvement = result_roi_per_trade / baseline_roi_per_trade
        print(f"  Improvement: {improvement:.2f}x ✅")
    print()

    # Assessment
    print("="*80)
    print("ASSESSMENT")
    print("="*80)
    print()

    if result['roi'] > baseline_roi:
        print(f"🚀 AMAZING! Outside Bar Only BEATS baseline!")
        print(f"   ROI: {result['roi']:.2f}% vs {baseline_roi:.2f}%")
        print(f"   Improvement: +{result['roi'] - baseline_roi:.2f}%")
        print(f"   {trade_reduction:.0f}% fewer trades!")
        print()
        print("✅ USE THIS STRATEGY!")
    elif result['roi'] > baseline_roi * 0.95:
        print(f"✅ GREAT! Similar ROI with fewer trades")
        print(f"   ROI: {result['roi']:.2f}% (vs {baseline_roi:.2f}%)")
        print(f"   Trade reduction: {trade_reduction:.0f}%")
        print(f"   Better quality, less commission!")
        print()
        print("✅ CONSIDER THIS STRATEGY!")
    elif result['roi'] > baseline_roi * 0.80:
        print(f"⚠️  Good but not amazing")
        print(f"   ROI: {result['roi']:.2f}% (vs {baseline_roi:.2f}%)")
        print(f"   Trade-off: {trade_reduction:.0f}% fewer trades")
    else:
        print(f"❌ Baseline is better")
        print(f"   Stick with both patterns")

    print()
    print("="*80)


if __name__ == '__main__':
    main()
