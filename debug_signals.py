#!/usr/bin/env python3
"""
Debug: Neden sinyal üretmiyor?
"""

import pandas as pd
import numpy as np

def load_csv_data(csv_path):
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

def detect_fractal(df):
    if len(df) < 3:
        return None, 0

    curr = df.iloc[-1]
    prev1 = df.iloc[-2]
    prev2 = df.iloc[-3]

    # Trending Up
    if (curr['close'] > prev1['close'] > prev2['close'] and
        curr['high'] > prev1['high'] > prev2['high']):
        body = abs(curr['close'] - curr['open'])
        range_val = curr['high'] - curr['low']
        if range_val > 0:
            strength = int((body / range_val) * 100)
            return 'Trending Up', strength

    # Outside Bar
    elif (curr['high'] > prev1['high'] and
          curr['low'] < prev1['low'] and
          curr['close'] > curr['open']):
        body = abs(curr['close'] - curr['open'])
        range_val = curr['high'] - curr['low']
        if range_val > 0:
            strength = int((body / range_val) * 100)
            return 'Outside Bar', strength

    return None, 0

# Load data
print("Loading data...")
csv_path = '/home/voidstring/Desktop/jesse_real/btc_15m_data_2018_to_2025.csv'
df_15m = load_csv_data(csv_path)
df_4h = resample_to_4h(df_15m)

print(f"Total 15m candles: {len(df_15m)}")
print(f"Date range: {df_15m.index[0]} to {df_15m.index[-1]}")
print()

# Test April 2025 period (paper trading start point)
start_idx = len(df_15m) - 20000
print(f"Testing from index {start_idx}: {df_15m.index[start_idx]}")
print()

# Check signals in first 1000 candles
signal_count = 0
fractal_count = 0
trend_filter_pass = 0

for i in range(start_idx + 200, start_idx + 1000):
    if i >= len(df_15m):
        break

    # Get recent data
    df_recent = df_15m.iloc[max(0, i-200):i]

    # Get 4h data
    current_time = df_15m.index[i]
    df_4h_recent = df_4h[df_4h.index <= current_time].tail(100)

    if len(df_recent) < 100 or len(df_4h_recent) < 50:
        continue

    # Check fractal
    pattern, strength = detect_fractal(df_recent)

    if pattern in ['Trending Up', 'Outside Bar'] and strength >= 50:
        fractal_count += 1

        # Check 4h trend
        df_4h_recent['ema_50'] = df_4h_recent['close'].ewm(span=50, adjust=False).mean()

        if df_4h_recent['close'].iloc[-1] > df_4h_recent['ema_50'].iloc[-1]:
            trend_filter_pass += 1
            signal_count += 1

            if signal_count <= 5:
                print(f"✅ SIGNAL #{signal_count}")
                print(f"   Time: {current_time}")
                print(f"   Pattern: {pattern}, Strength: {strength}")
                print(f"   Price: {df_recent['close'].iloc[-1]:.2f}")
                print(f"   4h Close: {df_4h_recent['close'].iloc[-1]:.2f}")
                print(f"   4h EMA50: {df_4h_recent['ema_50'].iloc[-1]:.2f}")
                print()

print("="*60)
print(f"Results from {start_idx} to {start_idx + 1000} (800 candles):")
print(f"Fractal patterns found: {fractal_count}")
print(f"4h trend filter passed: {trend_filter_pass}")
print(f"TOTAL VALID SIGNALS: {signal_count}")
print("="*60)

if signal_count == 0:
    print("\n⚠️  PROBLEM: No signals found!")
    print("\nChecking each condition separately:\n")

    # Check just fractals
    test_idx = start_idx + 500
    df_test = df_15m.iloc[test_idx-200:test_idx]
    pattern, strength = detect_fractal(df_test)
    print(f"Fractal at index {test_idx}: {pattern}, strength {strength}")

    # Check 4h trend
    current_time = df_15m.index[test_idx]
    df_4h_test = df_4h[df_4h.index <= current_time].tail(100)
    df_4h_test['ema_50'] = df_4h_test['close'].ewm(span=50, adjust=False).mean()
    print(f"4h Close: {df_4h_test['close'].iloc[-1]:.2f}")
    print(f"4h EMA50: {df_4h_test['ema_50'].iloc[-1]:.2f}")
    print(f"4h Trend Up: {df_4h_test['close'].iloc[-1] > df_4h_test['ema_50'].iloc[-1]}")
