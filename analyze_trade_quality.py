#!/usr/bin/env python3
"""
Trade Quality Analysis
=====================

Analyze which conditions produce the best trades:
1. Best fractal patterns
2. Best market conditions (ADX, volatility)
3. Best trend strength
4. Volume patterns
5. Time of day
6. Multi-timeframe alignment

Goal: Find filters to reduce trade count while increasing profit per trade
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


def backtest_with_analysis(df_15m, df_4h):
    """Run backtest and collect detailed trade analysis"""
    print("Running backtest with detailed analysis...")

    leverage = 10
    base_position_size = 0.05
    base_tp = 0.007
    base_sl = 0.0035
    commission = 0.0004

    # Prep data
    df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()
    df_4h['ema_20'] = df_4h['close'].ewm(span=20, adjust=False).mean()

    # 4h trend strength
    df_4h['ema_slope'] = df_4h['ema_50'].diff() / df_4h['ema_50']
    df_4h['trend_strength'] = np.where(
        df_4h['close'] > df_4h['ema_50'],
        (df_4h['close'] - df_4h['ema_50']) / df_4h['ema_50'],
        0
    )

    for col in ['close', 'ema_50', 'ema_20', 'ema_slope', 'trend_strength']:
        df_15m[f'4h_{col}'] = df_15m.index.map(
            lambda dt: df_4h[df_4h.index <= dt][col].iloc[-1]
            if len(df_4h[df_4h.index <= dt]) > 0 else np.nan
        )

    # 15m indicators
    df_15m['atr'] = calculate_atr(df_15m, 14)
    df_15m['adx'] = calculate_adx(df_15m, 14)
    df_15m['baseline_atr'] = df_15m['atr'].rolling(100, min_periods=1).mean()
    df_15m['vol_ratio'] = df_15m['atr'] / df_15m['baseline_atr']

    # Volume indicators
    df_15m['volume_ma'] = df_15m['volume'].rolling(20).mean()
    df_15m['volume_ratio'] = df_15m['volume'] / df_15m['volume_ma']

    # Price momentum
    df_15m['momentum'] = df_15m['close'].pct_change(5)

    # Fractal detection
    df_15m['fractal_pattern'] = None
    df_15m['fractal_strength'] = 0
    df_15m['fractal_consistency'] = 0  # New: how clean the fractal is

    print("Detecting fractals with quality metrics...")
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

                # Consistency: how clean are the closes/highs progression
                close_consistency = min(
                    (curr['close'] - prev1['close']) / curr['close'],
                    (prev1['close'] - prev2['close']) / prev1['close']
                ) * 100

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

                # Consistency for outside bar: body ratio
                consistency = (body / range_val) * 100

                df_15m.iloc[i, df_15m.columns.get_loc('fractal_pattern')] = 'Outside Bar'
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_strength')] = strength
                df_15m.iloc[i, df_15m.columns.get_loc('fractal_consistency')] = consistency

    df_15m.dropna(inplace=True)
    print("Fractals detected!")

    # Backtest with detailed tracking
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
            # Adaptive features (same as before)
            vol_ratio = row['vol_ratio']
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

                    # Entry conditions (for analysis)
                    'entry_fractal_pattern': row['fractal_pattern'],
                    'entry_fractal_strength': row['fractal_strength'],
                    'entry_fractal_consistency': row['fractal_consistency'],
                    'entry_adx': row['adx'],
                    'entry_vol_ratio': vol_ratio,
                    'entry_4h_trend_strength': row['4h_trend_strength'],
                    'entry_4h_ema_slope': row['4h_ema_slope'],
                    'entry_volume_ratio': row['volume_ratio'],
                    'entry_momentum': row['momentum'],
                    'entry_hour': idx.hour,
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

                # Store detailed trade info
                trade_record = {
                    'entry_time': current_trade['entry_time'],
                    'exit_time': idx,
                    'exit_type': exit_type,
                    'pnl': net_pnl,
                    'pnl_percent': (net_pnl / current_trade['collateral']) * 100,
                    'duration_minutes': (idx - current_trade['entry_time']).total_seconds() / 60,

                    # Entry conditions
                    'fractal_pattern': current_trade['entry_fractal_pattern'],
                    'fractal_strength': current_trade['entry_fractal_strength'],
                    'fractal_consistency': current_trade['entry_fractal_consistency'],
                    'adx': current_trade['entry_adx'],
                    'vol_ratio': current_trade['entry_vol_ratio'],
                    '4h_trend_strength': current_trade['entry_4h_trend_strength'],
                    '4h_ema_slope': current_trade['entry_4h_ema_slope'],
                    'volume_ratio': current_trade['entry_volume_ratio'],
                    'momentum': current_trade['entry_momentum'],
                    'entry_hour': current_trade['entry_hour'],
                }
                trades.append(trade_record)

                current_trade = None

    return pd.DataFrame(trades)


def analyze_trades(trades_df):
    """Analyze trade quality by different conditions"""
    print("\n" + "="*80)
    print("TRADE QUALITY ANALYSIS")
    print("="*80)
    print()

    # Overall stats
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]

    print(f"Total Trades: {len(trades_df)}")
    print(f"Wins: {len(wins)} ({len(wins)/len(trades_df)*100:.1f}%)")
    print(f"Losses: {len(losses)} ({len(losses)/len(trades_df)*100:.1f}%)")
    print(f"Avg PnL per trade: ${trades_df['pnl'].mean():.2f}")
    print(f"Avg Win: ${wins['pnl'].mean():.2f}")
    print(f"Avg Loss: ${losses['pnl'].mean():.2f}")
    print()

    # 1. Fractal Pattern Analysis
    print("="*80)
    print("1. FRACTAL PATTERN QUALITY")
    print("="*80)
    print()

    for pattern in trades_df['fractal_pattern'].unique():
        pattern_trades = trades_df[trades_df['fractal_pattern'] == pattern]
        pattern_wins = pattern_trades[pattern_trades['pnl'] > 0]

        print(f"{pattern}:")
        print(f"  Trades: {len(pattern_trades)}")
        print(f"  Win Rate: {len(pattern_wins)/len(pattern_trades)*100:.1f}%")
        print(f"  Avg PnL: ${pattern_trades['pnl'].mean():.2f}")
        print(f"  Total PnL: ${pattern_trades['pnl'].sum():.2f}")
        print()

    # 2. Fractal Strength Analysis
    print("="*80)
    print("2. FRACTAL STRENGTH IMPACT")
    print("="*80)
    print()

    strength_bins = [0, 50, 60, 70, 80, 100]
    trades_df['strength_bin'] = pd.cut(trades_df['fractal_strength'], bins=strength_bins)

    for bin in trades_df['strength_bin'].cat.categories:
        bin_trades = trades_df[trades_df['strength_bin'] == bin]
        if len(bin_trades) > 0:
            bin_wins = bin_trades[bin_trades['pnl'] > 0]
            print(f"Strength {bin}:")
            print(f"  Trades: {len(bin_trades)}")
            print(f"  Win Rate: {len(bin_wins)/len(bin_trades)*100:.1f}%")
            print(f"  Avg PnL: ${bin_trades['pnl'].mean():.2f}")
            print()

    # 3. ADX (Trend Strength) Analysis
    print("="*80)
    print("3. ADX (TREND STRENGTH) IMPACT")
    print("="*80)
    print()

    adx_bins = [0, 20, 25, 30, 40, 100]
    trades_df['adx_bin'] = pd.cut(trades_df['adx'], bins=adx_bins)

    for bin in trades_df['adx_bin'].cat.categories:
        bin_trades = trades_df[trades_df['adx_bin'] == bin]
        if len(bin_trades) > 0:
            bin_wins = bin_trades[bin_trades['pnl'] > 0]
            print(f"ADX {bin}:")
            print(f"  Trades: {len(bin_trades)}")
            print(f"  Win Rate: {len(bin_wins)/len(bin_trades)*100:.1f}%")
            print(f"  Avg PnL: ${bin_trades['pnl'].mean():.2f}")
            print()

    # 4. 4h Trend Strength Analysis
    print("="*80)
    print("4. 4H TREND STRENGTH IMPACT")
    print("="*80)
    print()

    trend_bins = [0, 0.01, 0.02, 0.05, 0.10, 1.0]
    trades_df['trend_bin'] = pd.cut(trades_df['4h_trend_strength'], bins=trend_bins)

    for bin in trades_df['trend_bin'].cat.categories:
        bin_trades = trades_df[trades_df['trend_bin'] == bin]
        if len(bin_trades) > 0:
            bin_wins = bin_trades[bin_trades['pnl'] > 0]
            print(f"Trend Strength {bin}:")
            print(f"  Trades: {len(bin_trades)}")
            print(f"  Win Rate: {len(bin_wins)/len(bin_trades)*100:.1f}%")
            print(f"  Avg PnL: ${bin_trades['pnl'].mean():.2f}")
            print()

    # 5. Volume Ratio Analysis
    print("="*80)
    print("5. VOLUME IMPACT")
    print("="*80)
    print()

    vol_bins = [0, 0.8, 1.2, 1.5, 2.0, 10.0]
    trades_df['vol_bin'] = pd.cut(trades_df['volume_ratio'], bins=vol_bins)

    for bin in trades_df['vol_bin'].cat.categories:
        bin_trades = trades_df[trades_df['vol_bin'] == bin]
        if len(bin_trades) > 0:
            bin_wins = bin_trades[bin_trades['pnl'] > 0]
            print(f"Volume Ratio {bin}:")
            print(f"  Trades: {len(bin_trades)}")
            print(f"  Win Rate: {len(bin_wins)/len(bin_trades)*100:.1f}%")
            print(f"  Avg PnL: ${bin_trades['pnl'].mean():.2f}")
            print()

    # 6. Time of Day Analysis
    print("="*80)
    print("6. TIME OF DAY IMPACT")
    print("="*80)
    print()

    hour_bins = [0, 6, 12, 18, 24]
    hour_labels = ['Night (0-6)', 'Morning (6-12)', 'Afternoon (12-18)', 'Evening (18-24)']
    trades_df['hour_bin'] = pd.cut(trades_df['entry_hour'], bins=hour_bins, labels=hour_labels, include_lowest=True)

    for bin in hour_labels:
        bin_trades = trades_df[trades_df['hour_bin'] == bin]
        if len(bin_trades) > 0:
            bin_wins = bin_trades[bin_trades['pnl'] > 0]
            print(f"{bin}:")
            print(f"  Trades: {len(bin_trades)}")
            print(f"  Win Rate: {len(bin_wins)/len(bin_trades)*100:.1f}%")
            print(f"  Avg PnL: ${bin_trades['pnl'].mean():.2f}")
            print()

    # 7. Best Combinations
    print("="*80)
    print("7. BEST TRADE CONDITIONS (Top Quality)")
    print("="*80)
    print()

    # Find trades with multiple strong conditions
    quality_trades = trades_df[
        (trades_df['fractal_strength'] >= 60) &
        (trades_df['adx'] >= 25) &
        (trades_df['4h_trend_strength'] >= 0.02) &
        (trades_df['volume_ratio'] >= 1.2)
    ]

    quality_wins = quality_trades[quality_trades['pnl'] > 0]

    print(f"High Quality Trades (multiple filters):")
    print(f"  Count: {len(quality_trades)} ({len(quality_trades)/len(trades_df)*100:.1f}% of all)")
    print(f"  Win Rate: {len(quality_wins)/len(quality_trades)*100:.1f}%")
    print(f"  Avg PnL: ${quality_trades['pnl'].mean():.2f}")
    print(f"  Total PnL: ${quality_trades['pnl'].sum():.2f}")
    print()

    regular_trades = trades_df[
        ~((trades_df['fractal_strength'] >= 60) &
          (trades_df['adx'] >= 25) &
          (trades_df['4h_trend_strength'] >= 0.02) &
          (trades_df['volume_ratio'] >= 1.2))
    ]

    regular_wins = regular_trades[regular_trades['pnl'] > 0]

    print(f"Regular Trades (lower quality):")
    print(f"  Count: {len(regular_trades)} ({len(regular_trades)/len(trades_df)*100:.1f}% of all)")
    print(f"  Win Rate: {len(regular_wins)/len(regular_trades)*100:.1f}%")
    print(f"  Avg PnL: ${regular_trades['pnl'].mean():.2f}")
    print(f"  Total PnL: ${regular_trades['pnl'].sum():.2f}")
    print()

    # ROI Comparison
    quality_roi = (quality_trades['pnl'].sum() / 10000) * 100
    regular_roi = (regular_trades['pnl'].sum() / 10000) * 100

    print("="*80)
    print("ROI COMPARISON")
    print("="*80)
    print()
    print(f"High Quality Trades ROI: {quality_roi:.2f}%")
    print(f"Regular Trades ROI: {regular_roi:.2f}%")
    print(f"Total ROI: {(trades_df['pnl'].sum() / 10000) * 100:.2f}%")
    print()

    if quality_roi / len(quality_trades) > regular_roi / len(regular_trades):
        improvement = (quality_roi / len(quality_trades)) / (regular_roi / len(regular_trades))
        print(f"✅ High quality trades are {improvement:.2f}x more profitable per trade!")

    return quality_trades, regular_trades


def main():
    print("="*80)
    print("TRADE QUALITY ANALYSIS - 7 YEARS")
    print("="*80)
    print()

    # Load data
    csv_path = '/home/voidstring/Desktop/jesse_real/btc_15m_data_2018_to_2025.csv'
    df_15m = load_csv_data(csv_path)
    df_4h = resample_to_4h(df_15m)

    print(f"Data: {df_15m.index[0]} to {df_15m.index[-1]}")
    print(f"Total: {len(df_15m)} candles (15m)")
    print()

    # Run backtest with detailed tracking
    trades_df = backtest_with_analysis(df_15m, df_4h)

    # Analyze
    quality_trades, regular_trades = analyze_trades(trades_df)

    # Save results
    trades_df.to_csv('trade_analysis_detailed.csv', index=False)
    print("\n✅ Detailed trade data saved to trade_analysis_detailed.csv")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print()
    print("Based on this analysis, we can create improved strategies:")
    print()
    print("1. **High Quality Only Strategy**")
    print("   - Only trade when multiple conditions align")
    print("   - Expected: 1/3 trades, 2-3x profit per trade")
    print()
    print("2. **Trend Focused Strategy**")
    print("   - Strong 4h trends only (>2% above EMA)")
    print("   - High ADX (>25) for trend confirmation")
    print()
    print("3. **Volume Breakout Strategy**")
    print("   - Only trade high volume fractals (>1.5x avg)")
    print("   - Better follow-through")
    print()
    print("4. **Time-Based Strategy**")
    print("   - Avoid low-performing time windows")
    print("   - Focus on best hours")
    print()
    print("="*80)


if __name__ == '__main__':
    main()
