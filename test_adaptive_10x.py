#!/usr/bin/env python3
"""
Quick Test: 10x Adaptive Strategy
==================================
"""

import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime


def load_data(start_date, end_date):
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

    start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)

    # 15m
    query_15m = f"""
        SELECT timestamp, open, high, low, close, volume
        FROM candle
        WHERE symbol = 'BTC-USDT'
        AND exchange = 'Binance Futures'
        AND timeframe = '15m'
        AND timestamp >= {start_ts}
        AND timestamp <= {end_ts}
        ORDER BY timestamp
    """
    df_15m = pd.read_sql_query(query_15m, conn)
    df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
    df_15m.set_index('timestamp', inplace=True)

    # 4h
    query_4h = f"""
        SELECT timestamp, open, high, low, close, volume
        FROM candle
        WHERE symbol = 'BTC-USDT'
        AND exchange = 'Binance Futures'
        AND timeframe = '4h'
        AND timestamp >= {start_ts}
        AND timestamp <= {end_ts}
        ORDER BY timestamp
    """
    df_4h = pd.read_sql_query(query_4h, conn)
    df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h.set_index('timestamp', inplace=True)

    conn.close()
    return df_15m, df_4h


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
    close = df['close'].values

    # Simplified ADX
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


def backtest_adaptive(df_15m, df_4h):
    print("Running 10x ADAPTIVE backtest...")

    # Config
    leverage = 10
    base_position_size = 0.05
    base_tp = 0.007
    base_sl = 0.0035
    commission = 0.0004

    # Prep data
    df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()

    for col in ['close', 'ema_50']:
        df_15m[f'4h_{col}'] = df_15m.index.map(
            lambda dt: df_4h[df_4h.index <= dt][col].iloc[-1]
            if len(df_4h[df_4h.index <= dt]) > 0 else np.nan
        )

    # ATR and ADX
    df_15m['atr'] = calculate_atr(df_15m, 14)
    df_15m['adx'] = calculate_adx(df_15m, 14)

    # Baseline ATR (100-period rolling mean)
    df_15m['baseline_atr'] = df_15m['atr'].rolling(100, min_periods=1).mean()

    # Fractal
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
        # Update peak
        if balance > peak_balance:
            peak_balance = balance

        if current_trade is None:
            # === ADAPTIVE FEATURES ===

            # 1. Volatility ratio
            vol_ratio = row['atr'] / row['baseline_atr'] if row['baseline_atr'] > 0 else 1.0

            # 2. Adaptive TP/SL
            adaptive_tp = base_tp * vol_ratio
            adaptive_sl = base_sl * vol_ratio
            adaptive_tp = np.clip(adaptive_tp, 0.004, 0.015)
            adaptive_sl = np.clip(adaptive_sl, 0.002, 0.008)

            # 3. Market regime
            adx = row['adx']
            if adx > 25:  # Trending
                tp_multiplier = 1.2
                strength_adj = -5
            elif adx < 20:  # Ranging
                tp_multiplier = 0.8
                strength_adj = +10
            else:
                tp_multiplier = 1.0
                strength_adj = 0

            adaptive_tp *= tp_multiplier
            min_strength = 50 + strength_adj

            # 4. Drawdown protection
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
                dd_multiplier = 0  # Stop trading

            position_size = base_position_size * dd_multiplier

            if position_size == 0:
                continue

            # 5. Performance adaptation
            if len(recent_trades) >= 10:
                win_rate = sum([1 for t in recent_trades[-20:] if t > 0]) / len(recent_trades[-20:])
                if win_rate > 0.6:
                    position_size *= 1.1
                elif win_rate < 0.4:
                    position_size *= 0.9

            position_size = np.clip(position_size, 0.01, 0.08)

            # Entry check
            if (dd >= -0.05 and
                row['fractal_pattern'] in ['Trending Up', 'Outside Bar'] and
                row['fractal_strength'] >= min_strength and
                row['4h_close'] > row['4h_ema_50']):

                position_value = balance * position_size * leverage
                entry_commission = position_value * commission

                current_trade = {
                    'entry_time': idx,
                    'entry_price': row['close'],
                    'position_value': position_value,
                    'collateral': balance * position_size,
                    'tp_price': row['close'] * (1 + adaptive_tp),
                    'sl_price': row['close'] * (1 - adaptive_sl),
                    'highest_price': row['close'],
                    'trailing_active': False,
                    'trailing_stop': None,
                    'entry_commission': entry_commission,
                    'adaptive_tp': adaptive_tp,
                    'adaptive_sl': adaptive_sl,
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

                trades.append({
                    'entry_time': current_trade['entry_time'],
                    'exit_time': idx,
                    'exit_type': exit_type,
                    'pnl': net_pnl,
                    'adaptive_tp': current_trade['adaptive_tp'],
                    'adaptive_sl': current_trade['adaptive_sl'],
                })

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

        # TP/SL statistics
        avg_tp = trades_df['adaptive_tp'].mean() * 100
        avg_sl = trades_df['adaptive_sl'].mean() * 100
    else:
        win_rate = 0
        profit_factor = 0
        max_dd = 0
        exit_counts = {}
        avg_tp = 0
        avg_sl = 0

    return {
        'roi': roi,
        'final_balance': balance,
        'num_trades': len(trades_df),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_dd': max_dd,
        'exit_counts': exit_counts,
        'avg_adaptive_tp': avg_tp,
        'avg_adaptive_sl': avg_sl,
    }


def main():
    print("="*80)
    print("10x ADAPTIVE STRATEGY TEST")
    print("="*80)
    print()

    # Load data
    df_15m, df_4h = load_data('2023-01-01', '2024-10-31')
    print(f"Data loaded: {len(df_15m)} candles (22 months)")
    print()

    # Backtest
    result = backtest_adaptive(df_15m, df_4h)

    # Results
    print("="*80)
    print("RESULTS - 10x ADAPTIVE")
    print("="*80)
    print()
    print(f"ROI: {result['roi']:.2f}%")
    print(f"Final Balance: ${result['final_balance']:.2f}")
    print(f"Trades: {result['num_trades']}")
    print(f"Win Rate: {result['win_rate']:.1f}%")
    print(f"Profit Factor: {result['profit_factor']:.2f}")
    print(f"Max Drawdown: {result['max_dd']:.2f}%")
    print()
    print(f"Avg Adaptive TP: {result['avg_adaptive_tp']:.2f}%")
    print(f"Avg Adaptive SL: {result['avg_adaptive_sl']:.2f}%")
    print()

    if result['exit_counts']:
        print("Exit Distribution:")
        for exit_type, count in result['exit_counts'].items():
            pct = (count / result['num_trades']) * 100
            print(f"  {exit_type}: {count} ({pct:.1f}%)")
    print()

    # Comparison
    print("="*80)
    print("COMPARISON: Baseline vs Adaptive (10x)")
    print("="*80)
    print()
    print(f"{'Metric':<20} {'Baseline':<15} {'Adaptive':<15} {'Diff':<10}")
    print("-"*80)

    adaptive_roi_str = f"{result['roi']:.2f}%"
    roi_diff_str = f"{result['roi']-36.88:+.2f}%"
    print(f"{'ROI':<20} {'36.88%':<15} {adaptive_roi_str:<15} {roi_diff_str:<10}")

    adaptive_wr_str = f"{result['win_rate']:.1f}%"
    wr_diff_str = f"{result['win_rate']-52.1:+.1f}%"
    print(f"{'Win Rate':<20} {'52.1%':<15} {adaptive_wr_str:<15} {wr_diff_str:<10}")

    adaptive_dd_str = f"{result['max_dd']:.2f}%"
    dd_diff_str = f"{result['max_dd']+2.95:.2f}%"
    print(f"{'Max DD':<20} {'-2.95%':<15} {adaptive_dd_str:<15} {dd_diff_str:<10}")

    adaptive_pf_str = f"{result['profit_factor']:.2f}"
    pf_diff_str = f"{result['profit_factor']-1.36:+.2f}"
    print(f"{'Profit Factor':<20} {'1.36':<15} {adaptive_pf_str:<15} {pf_diff_str:<10}")
    print()

    if result['roi'] > 36.88:
        improvement = ((result['roi'] - 36.88) / 36.88) * 100
        print(f"✅ Adaptive is {improvement:.1f}% BETTER than Baseline!")
    elif result['roi'] > 30:
        print(f"✅ Adaptive is still VERY GOOD (>30% ROI)")
    else:
        print(f"⚠️  Adaptive underperformed baseline")

    print()
    print("="*80)


if __name__ == '__main__':
    main()
