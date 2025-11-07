#!/usr/bin/env python3
"""
Quick Test: 20x Adaptive Strategy
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
    print("Running 20x ADAPTIVE backtest...")

    # Config - ADJUSTED FOR 20x LEVERAGE
    leverage = 20
    base_position_size = 0.03  # 3% capital (60% exposure with 20x)
    base_tp = 0.006  # Slightly tighter TP (0.6% vs 0.7%)
    base_sl = 0.003  # Tighter SL (0.3% vs 0.35%)
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
    liquidation_count = 0

    for idx, row in df_15m.iterrows():
        # Update peak
        if balance > peak_balance:
            peak_balance = balance

        if current_trade is None:
            # === ADAPTIVE FEATURES ===

            # 1. Volatility ratio
            vol_ratio = row['atr'] / row['baseline_atr'] if row['baseline_atr'] > 0 else 1.0

            # 2. Adaptive TP/SL (tighter ranges for 20x)
            adaptive_tp = base_tp * vol_ratio
            adaptive_sl = base_sl * vol_ratio
            adaptive_tp = np.clip(adaptive_tp, 0.003, 0.012)  # 0.3% - 1.2%
            adaptive_sl = np.clip(adaptive_sl, 0.0015, 0.006)  # 0.15% - 0.6%

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

            # 4. Drawdown protection (MORE AGGRESSIVE for 20x)
            dd = (balance - peak_balance) / peak_balance if peak_balance > 0 else 0

            if dd >= 0:
                dd_multiplier = 1.0
            elif dd > -0.005:  # -0.5%
                dd_multiplier = 1.0
            elif dd > -0.01:   # -1%
                dd_multiplier = 0.8
            elif dd > -0.02:   # -2%
                dd_multiplier = 0.5
            elif dd > -0.03:   # -3%
                dd_multiplier = 0.2
            else:
                dd_multiplier = 0  # Stop trading at -3% DD

            position_size = base_position_size * dd_multiplier

            if position_size == 0:
                continue

            # 5. Performance adaptation
            if len(recent_trades) >= 10:
                win_rate = sum([1 for t in recent_trades[-20:] if t > 0]) / len(recent_trades[-20:])
                if win_rate > 0.6:
                    position_size *= 1.05  # Smaller bonus for 20x
                elif win_rate < 0.4:
                    position_size *= 0.85  # Bigger reduction for 20x

            position_size = np.clip(position_size, 0.01, 0.05)  # Max 5% (100% exposure at 20x)

            # Entry check
            if (dd >= -0.03 and  # Stricter DD limit
                row['fractal_pattern'] in ['Trending Up', 'Outside Bar'] and
                row['fractal_strength'] >= min_strength and
                row['4h_close'] > row['4h_ema_50']):

                position_value = balance * position_size * leverage
                entry_commission = position_value * commission
                collateral = balance * position_size

                # Calculate liquidation price (20x leverage)
                liquidation_price = row['close'] * (1 - (1 / leverage) + 0.004)  # 4.6% below entry

                current_trade = {
                    'entry_time': idx,
                    'entry_price': row['close'],
                    'position_value': position_value,
                    'collateral': collateral,
                    'tp_price': row['close'] * (1 + adaptive_tp),
                    'sl_price': row['close'] * (1 - adaptive_sl),
                    'liquidation_price': liquidation_price,
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
                if current_price >= current_trade['entry_price'] * 1.004:  # 0.4% activation
                    current_trade['trailing_active'] = True
                    current_trade['trailing_stop'] = current_price * 0.999  # 0.1% distance

            if current_trade['trailing_active']:
                new_trailing = current_trade['highest_price'] * 0.999
                if new_trailing > current_trade['trailing_stop']:
                    current_trade['trailing_stop'] = new_trailing

            # Check exits
            exit_type = None
            exit_price = None

            # LIQUIDATION CHECK (most important for 20x)
            if low_price <= current_trade['liquidation_price']:
                exit_type = 'LIQUIDATION'
                exit_price = current_trade['liquidation_price']
                liquidation_count += 1
            elif low_price <= current_trade['sl_price']:
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

                if exit_type == 'LIQUIDATION':
                    # Lose all collateral
                    net_pnl = -current_trade['collateral']
                else:
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
        'liquidations': liquidation_count,
    }


def main():
    print("="*80)
    print("20x ADAPTIVE STRATEGY TEST")
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
    print("RESULTS - 20x ADAPTIVE")
    print("="*80)
    print()
    print(f"ROI: {result['roi']:.2f}%")
    print(f"Final Balance: ${result['final_balance']:.2f}")
    print(f"Trades: {result['num_trades']}")
    print(f"Win Rate: {result['win_rate']:.1f}%")
    print(f"Profit Factor: {result['profit_factor']:.2f}")
    print(f"Max Drawdown: {result['max_dd']:.2f}%")
    print(f"Liquidations: {result['liquidations']}")
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
    print("COMPARISON: Baseline 20x vs Adaptive 20x vs Adaptive 10x")
    print("="*80)
    print()
    print(f"{'Metric':<20} {'Baseline 20x':<15} {'Adaptive 20x':<15} {'Adaptive 10x':<15}")
    print("-"*80)

    baseline_roi_str = "-3.62%"
    adaptive_20x_roi_str = f"{result['roi']:.2f}%"
    adaptive_10x_roi_str = "45.65%"
    print(f"{'ROI':<20} {baseline_roi_str:<15} {adaptive_20x_roi_str:<15} {adaptive_10x_roi_str:<15}")

    baseline_wr_str = "~48%"
    adaptive_20x_wr_str = f"{result['win_rate']:.1f}%"
    adaptive_10x_wr_str = "53.9%"
    print(f"{'Win Rate':<20} {baseline_wr_str:<15} {adaptive_20x_wr_str:<15} {adaptive_10x_wr_str:<15}")

    baseline_dd_str = "N/A"
    adaptive_20x_dd_str = f"{result['max_dd']:.2f}%"
    adaptive_10x_dd_str = "-2.57%"
    print(f"{'Max DD':<20} {baseline_dd_str:<15} {adaptive_20x_dd_str:<15} {adaptive_10x_dd_str:<15}")

    baseline_liq_str = "1"
    adaptive_20x_liq_str = f"{result['liquidations']}"
    adaptive_10x_liq_str = "0"
    print(f"{'Liquidations':<20} {baseline_liq_str:<15} {adaptive_20x_liq_str:<15} {adaptive_10x_liq_str:<15}")
    print()

    # Assessment
    print("="*80)
    print("ASSESSMENT")
    print("="*80)
    print()

    if result['liquidations'] > 0:
        print(f"⚠️  {result['liquidations']} LIQUIDATION(S) occurred - 20x too risky")
    else:
        print(f"✅ No liquidations!")

    if result['roi'] > 45.65:
        improvement = ((result['roi'] - 45.65) / 45.65) * 100
        print(f"✅ 20x Adaptive is {improvement:.1f}% BETTER than 10x Adaptive!")
        print(f"✅ Recommend 20x for higher risk tolerance")
    elif result['roi'] > 36.88:
        print(f"✅ 20x Adaptive BEATS 10x Baseline ({result['roi']:.2f}% vs 36.88%)")
        print(f"⚠️  But underperforms 10x Adaptive (45.65%)")
        print(f"⚠️  Stick with 10x Adaptive for better risk/reward")
    elif result['roi'] > 0:
        print(f"⚠️  20x Adaptive is positive but underperforms both:")
        print(f"   - 10x Baseline: 36.88%")
        print(f"   - 10x Adaptive: 45.65%")
        print(f"❌ Do NOT use 20x - stick with 10x")
    else:
        print(f"❌ 20x Adaptive is NEGATIVE ({result['roi']:.2f}%)")
        print(f"❌ FAILED like baseline 20x (-3.62%)")
        print(f"❌ 20x is TOO RISKY - use 10x instead")

    print()
    print("="*80)
    print("RECOMMENDATION")
    print("="*80)
    print()

    if result['roi'] > 45 and result['liquidations'] == 0:
        print("🚀 20x Adaptive is viable! Higher risk, higher reward.")
    elif result['roi'] > 36 and result['liquidations'] == 0:
        print("⚡ 20x Adaptive works but 10x Adaptive is safer with similar returns.")
    else:
        print("✅ STICK WITH 10x ADAPTIVE:")
        print("   - ROI: 45.65%")
        print("   - Win Rate: 53.9%")
        print("   - Max DD: -2.57%")
        print("   - Liquidations: 0")
        print("   - Best risk/reward ratio!")

    print()
    print("="*80)


if __name__ == '__main__':
    main()
