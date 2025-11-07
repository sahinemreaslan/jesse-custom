#!/usr/bin/env python3
"""
Standalone Backtest (Redis gerektirmez)
========================================

Jesse CLI yerine direkt strateji test eder
"""

import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real/strategies')

from FractalTrend10x import FractalTrend10x
import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime


def load_data(start_date, end_date):
    """Load 15m and 4h data"""
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

    start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)

    # Load 15m
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

    # Load 4h
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


def simple_backtest(df_15m, df_4h):
    """
    Simplified backtest using our validated logic
    """
    print("Running backtest...")

    # Configuration (from FractalTrend10x)
    config = {
        'min_fractal_strength': 50,
        'leverage': 10,
        'position_size': 0.05,
        'tp_percent': 0.007,
        'sl_percent': 0.0035,
        'trailing_activation': 0.005,
        'trailing_distance': 0.002,
        'commission': 0.0004,
    }

    # EMA50 on 4h
    df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()

    # Merge 4h into 15m
    for col in ['close', 'ema_50']:
        df_15m[f'4h_{col}'] = df_15m.index.map(
            lambda dt: df_4h[df_4h.index <= dt][col].iloc[-1]
            if len(df_4h[df_4h.index <= dt]) > 0 else np.nan
        )

    # Fractal analysis
    df_15m['fractal_pattern'] = None
    df_15m['fractal_strength'] = 0

    for i in range(2, len(df_15m)):
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

        # Outside Bar
        elif (curr['high'] > prev1['high'] and
              curr['low'] < prev1['low'] and
              curr['close'] > curr['open']):

            body = abs(curr['close'] - curr['open'])
            range_val = curr['high'] - curr['low']

            if range_val > 0:
                strength = int((body / range_val) * 100)
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_pattern')] = 'Outside Bar'
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_strength')] = strength

    # Drop NaN
    df_15m.dropna(inplace=True)

    # Backtest
    balance = 10000
    trades = []
    current_trade = None

    for idx, row in df_15m.iterrows():
        if current_trade is None:
            # Entry check
            if (row['fractal_pattern'] in ['Trending Up', 'Outside Bar'] and
                row['fractal_strength'] >= config['min_fractal_strength'] and
                row['4h_close'] > row['4h_ema_50']):

                # Open position
                position_value = balance * config['position_size'] * config['leverage']
                entry_commission = position_value * config['commission']

                current_trade = {
                    'entry_time': idx,
                    'entry_price': row['close'],
                    'position_value': position_value,
                    'collateral': balance * config['position_size'],
                    'tp_price': row['close'] * (1 + config['tp_percent']),
                    'sl_price': row['close'] * (1 - config['sl_percent']),
                    'highest_price': row['close'],
                    'trailing_active': False,
                    'trailing_stop': None,
                    'entry_commission': entry_commission,
                }

        else:
            # Exit check
            current_price = row['close']
            high_price = row['high']
            low_price = row['low']

            # Update highest
            if high_price > current_trade['highest_price']:
                current_trade['highest_price'] = high_price

            # Trailing activation
            if not current_trade['trailing_active']:
                if current_price >= current_trade['entry_price'] * (1 + config['trailing_activation']):
                    current_trade['trailing_active'] = True
                    current_trade['trailing_stop'] = current_price * (1 - config['trailing_distance'])

            # Update trailing
            if current_trade['trailing_active']:
                new_trailing = current_trade['highest_price'] * (1 - config['trailing_distance'])
                if new_trailing > current_trade['trailing_stop']:
                    current_trade['trailing_stop'] = new_trailing

            # Check exits
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
                exit_commission = current_trade['position_value'] * config['commission']
                price_change = (exit_price / current_trade['entry_price']) - 1
                leveraged_pnl = price_change * config['leverage']
                gross_pnl = current_trade['collateral'] * leveraged_pnl
                net_pnl = gross_pnl - current_trade['entry_commission'] - exit_commission

                balance += net_pnl

                trades.append({
                    'entry_time': current_trade['entry_time'],
                    'exit_time': idx,
                    'exit_type': exit_type,
                    'pnl': net_pnl,
                })

                current_trade = None

    # Results
    final_balance = balance
    roi = ((final_balance - 10000) / 10000) * 100

    trades_df = pd.DataFrame(trades)

    if len(trades_df) > 0:
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] <= 0]

        win_rate = len(wins) / len(trades_df) * 100
        total_profit = wins['pnl'].sum() if len(wins) > 0 else 0
        total_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1
        profit_factor = total_profit / total_loss

        # Drawdown
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
        'final_balance': final_balance,
        'num_trades': len(trades_df),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_dd': max_dd,
        'exit_counts': exit_counts,
    }


def main():
    print("="*80)
    print("STANDALONE BACKTEST - FractalTrend10x")
    print("="*80)
    print()

    # Test period
    start_date = '2024-10-01'
    end_date = '2024-10-31'

    print(f"Period: {start_date} → {end_date}")
    print()

    # Load data
    print("Loading data...")
    df_15m, df_4h = load_data(start_date, end_date)
    print(f"✅ Loaded: {len(df_15m)} x 15m candles, {len(df_4h)} x 4h candles")
    print()

    # Backtest
    result = simple_backtest(df_15m, df_4h)

    # Results
    print("="*80)
    print("RESULTS")
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

    # Expected comparison
    print("="*80)
    print("COMPARISON")
    print("="*80)
    print()
    print("Expected (1 month, validated backtest):")
    print("  ROI: ~2%")
    print("  Trades: 60-80")
    print("  Win Rate: ~52%")
    print()

    if result['roi'] > 1.5:
        print("✅ Performance looks good!")
    elif result['roi'] > 0:
        print("⚠️  Slightly below expected, but positive")
    else:
        print("❌ Negative - needs investigation")

    print()
    print("="*80)
    print("Next: Full 10-month test")
    print("Command: python standalone_backtest.py --full")
    print("="*80)


if __name__ == '__main__':
    main()
