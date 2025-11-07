#!/usr/bin/env python3
"""
Live Paper Trading Simulator
============================

Standalone paper trading that:
- Fetches latest candles from database
- Runs Adaptive strategy logic
- Simulates trades in real-time
- Logs performance

No Redis or Jesse CLI required!
"""

import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timedelta
import time
import json
import os


class LivePaperTrader:
    def __init__(self):
        # Config
        self.leverage = 10
        self.base_position_size = 0.05
        self.base_tp = 0.007
        self.base_sl = 0.0035
        self.commission = 0.0004

        # State
        self.balance = 10000
        self.initial_balance = 10000
        self.peak_balance = 10000
        self.current_trade = None
        self.trades = []
        self.recent_trades = []

        # Database
        self.conn = None
        self.connect_db()

        # Logs
        self.log_file = 'paper_trading_log.json'
        self.load_state()

    def connect_db(self):
        """Connect to PostgreSQL"""
        self.conn = psycopg2.connect(
            host='127.0.0.1',
            database='jesse_db',
            user='voidstring',
            password=''
        )

    def load_state(self):
        """Load previous state if exists"""
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r') as f:
                data = json.load(f)
                self.balance = data.get('balance', 10000)
                self.initial_balance = data.get('initial_balance', 10000)
                self.peak_balance = data.get('peak_balance', 10000)
                self.trades = data.get('trades', [])
                self.recent_trades = data.get('recent_trades', [])
                print(f"📂 Loaded state: Balance=${self.balance:.2f}")

    def save_state(self):
        """Save current state"""
        data = {
            'balance': self.balance,
            'initial_balance': self.initial_balance,
            'peak_balance': self.peak_balance,
            'trades': self.trades,
            'recent_trades': self.recent_trades,
            'last_update': datetime.now().isoformat(),
        }
        with open(self.log_file, 'w') as f:
            json.dump(data, f, indent=2)

    def fetch_recent_candles(self, timeframe='15m', limit=200):
        """Fetch recent candles from database"""
        query = f"""
            SELECT timestamp, open, high, low, close, volume
            FROM candle
            WHERE symbol = 'BTC-USDT'
            AND exchange = 'Binance Futures'
            AND timeframe = '{timeframe}'
            ORDER BY timestamp DESC
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, self.conn)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.sort_values('timestamp')
        df.set_index('timestamp', inplace=True)
        return df

    def calculate_atr(self, df, period=14):
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

    def calculate_adx(self, df, period=14):
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

        atr = self.calculate_atr(df, period)
        plus_di = 100 * pd.Series(plus_dm).ewm(span=period, adjust=False).mean() / (atr + 1e-10)
        minus_di = 100 * pd.Series(minus_dm).ewm(span=period, adjust=False).mean() / (atr + 1e-10)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.ewm(span=period, adjust=False).mean()

        return adx.values

    def detect_fractal(self, df):
        """Detect fractal pattern on latest candles"""
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

    def get_adaptive_params(self, df_15m, df_4h):
        """Calculate adaptive TP/SL and position size"""
        # ATR
        atr_current = self.calculate_atr(df_15m, 14)[-1]
        atr_baseline = np.mean(self.calculate_atr(df_15m, 14)[-100:])
        vol_ratio = atr_current / atr_baseline if atr_baseline > 0 else 1.0

        # Adaptive TP/SL
        adaptive_tp = self.base_tp * vol_ratio
        adaptive_sl = self.base_sl * vol_ratio
        adaptive_tp = np.clip(adaptive_tp, 0.004, 0.015)
        adaptive_sl = np.clip(adaptive_sl, 0.002, 0.008)

        # ADX (market regime)
        adx = self.calculate_adx(df_15m, 14)[-1]
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

        # Drawdown protection
        dd = (self.balance - self.peak_balance) / self.peak_balance if self.peak_balance > 0 else 0

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

        position_size = self.base_position_size * dd_multiplier

        # Performance adaptation
        if len(self.recent_trades) >= 10:
            win_rate = sum([1 for t in self.recent_trades[-20:] if t > 0]) / len(self.recent_trades[-20:])
            if win_rate > 0.6:
                position_size *= 1.1
            elif win_rate < 0.4:
                position_size *= 0.9

        position_size = np.clip(position_size, 0.01, 0.08)

        return {
            'adaptive_tp': adaptive_tp,
            'adaptive_sl': adaptive_sl,
            'position_size': position_size,
            'min_strength': min_strength,
            'dd': dd,
            'vol_ratio': vol_ratio,
            'adx': adx,
        }

    def check_entry(self):
        """Check if should enter trade"""
        if self.current_trade is not None:
            return  # Already in trade

        # Fetch data
        df_15m = self.fetch_recent_candles('15m', 200)
        df_4h = self.fetch_recent_candles('4h', 100)

        if len(df_15m) < 100 or len(df_4h) < 50:
            return

        # 4h trend filter
        df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()
        if df_4h['close'].iloc[-1] <= df_4h['ema_50'].iloc[-1]:
            return  # No 4h uptrend

        # Fractal pattern
        pattern, strength = self.detect_fractal(df_15m)

        # Adaptive params
        params = self.get_adaptive_params(df_15m, df_4h)

        if params['position_size'] == 0:
            print(f"⚠️  DD limit reached ({params['dd']:.2%}), stop trading")
            return

        # Entry check
        if (pattern in ['Trending Up', 'Outside Bar'] and
            strength >= params['min_strength']):

            entry_price = df_15m['close'].iloc[-1]
            position_value = self.balance * params['position_size'] * self.leverage
            entry_commission = position_value * self.commission

            self.current_trade = {
                'entry_time': df_15m.index[-1],
                'entry_price': entry_price,
                'position_value': position_value,
                'collateral': self.balance * params['position_size'],
                'tp_price': entry_price * (1 + params['adaptive_tp']),
                'sl_price': entry_price * (1 - params['adaptive_sl']),
                'highest_price': entry_price,
                'trailing_active': False,
                'trailing_stop': None,
                'entry_commission': entry_commission,
                'adaptive_tp': params['adaptive_tp'],
                'adaptive_sl': params['adaptive_sl'],
                'pattern': pattern,
                'strength': strength,
            }

            print(f"\n🚀 ENTRY: {pattern} (str={strength})")
            print(f"   Price: ${entry_price:,.2f}")
            print(f"   TP: ${self.current_trade['tp_price']:,.2f} ({params['adaptive_tp']:.2%})")
            print(f"   SL: ${self.current_trade['sl_price']:,.2f} ({params['adaptive_sl']:.2%})")
            print(f"   Size: {params['position_size']:.1%} (${position_value:,.0f})")
            print(f"   ADX: {params['adx']:.1f}, Vol Ratio: {params['vol_ratio']:.2f}")

    def check_exit(self):
        """Check if should exit trade"""
        if self.current_trade is None:
            return

        # Fetch latest candle
        df_15m = self.fetch_recent_candles('15m', 5)
        if len(df_15m) == 0:
            return

        current_price = df_15m['close'].iloc[-1]
        high_price = df_15m['high'].iloc[-1]
        low_price = df_15m['low'].iloc[-1]

        # Update highest
        if high_price > self.current_trade['highest_price']:
            self.current_trade['highest_price'] = high_price

        # Trailing activation
        if not self.current_trade['trailing_active']:
            if current_price >= self.current_trade['entry_price'] * 1.005:
                self.current_trade['trailing_active'] = True
                self.current_trade['trailing_stop'] = current_price * 0.998
                print(f"   📈 Trailing activated at ${current_price:,.2f}")

        # Update trailing
        if self.current_trade['trailing_active']:
            new_trailing = self.current_trade['highest_price'] * 0.998
            if new_trailing > self.current_trade['trailing_stop']:
                self.current_trade['trailing_stop'] = new_trailing

        # Check exits
        exit_type = None
        exit_price = None

        if low_price <= self.current_trade['sl_price']:
            exit_type = 'SL'
            exit_price = self.current_trade['sl_price']
        elif high_price >= self.current_trade['tp_price']:
            exit_type = 'TP'
            exit_price = self.current_trade['tp_price']
        elif self.current_trade['trailing_active'] and low_price <= self.current_trade['trailing_stop']:
            exit_type = 'Trailing'
            exit_price = self.current_trade['trailing_stop']

        if exit_type:
            exit_commission = self.current_trade['position_value'] * self.commission
            price_change = (exit_price / self.current_trade['entry_price']) - 1
            leveraged_pnl = price_change * self.leverage
            gross_pnl = self.current_trade['collateral'] * leveraged_pnl
            net_pnl = gross_pnl - self.current_trade['entry_commission'] - exit_commission

            self.balance += net_pnl
            self.recent_trades.append(net_pnl)
            if len(self.recent_trades) > 20:
                self.recent_trades.pop(0)

            # Update peak
            if self.balance > self.peak_balance:
                self.peak_balance = self.balance

            trade_record = {
                'entry_time': self.current_trade['entry_time'].isoformat(),
                'exit_time': df_15m.index[-1].isoformat(),
                'entry_price': self.current_trade['entry_price'],
                'exit_price': exit_price,
                'exit_type': exit_type,
                'pnl': net_pnl,
                'balance_after': self.balance,
                'pattern': self.current_trade['pattern'],
                'strength': self.current_trade['strength'],
            }
            self.trades.append(trade_record)

            # Print exit
            roi_trade = (net_pnl / self.current_trade['collateral']) * 100
            roi_total = ((self.balance - self.initial_balance) / self.initial_balance) * 100

            emoji = "✅" if net_pnl > 0 else "❌"
            print(f"\n{emoji} EXIT ({exit_type}): ${exit_price:,.2f}")
            print(f"   PnL: ${net_pnl:,.2f} ({roi_trade:+.2f}%)")
            print(f"   Balance: ${self.balance:,.2f} (ROI: {roi_total:+.2f}%)")
            print(f"   Trades: {len(self.trades)} | Win Rate: {self.get_win_rate():.1f}%")

            self.current_trade = None
            self.save_state()

    def get_win_rate(self):
        """Calculate win rate"""
        if len(self.trades) == 0:
            return 0
        wins = sum([1 for t in self.trades if t['pnl'] > 0])
        return (wins / len(self.trades)) * 100

    def print_status(self):
        """Print current status"""
        roi = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        dd = ((self.balance - self.peak_balance) / self.peak_balance) * 100 if self.peak_balance > 0 else 0

        print(f"\n📊 STATUS:")
        print(f"   Balance: ${self.balance:,.2f} (ROI: {roi:+.2f}%)")
        print(f"   Peak: ${self.peak_balance:,.2f} (DD: {dd:.2f}%)")
        print(f"   Trades: {len(self.trades)}")
        if len(self.trades) > 0:
            print(f"   Win Rate: {self.get_win_rate():.1f}%")

        if self.current_trade:
            current_price = self.fetch_recent_candles('15m', 1)['close'].iloc[-1]
            unrealized = ((current_price / self.current_trade['entry_price']) - 1) * self.leverage * self.current_trade['collateral']
            print(f"\n   🔄 OPEN TRADE:")
            print(f"      Entry: ${self.current_trade['entry_price']:,.2f}")
            print(f"      Current: ${current_price:,.2f}")
            print(f"      Unrealized: ${unrealized:+,.2f}")
            print(f"      TP: ${self.current_trade['tp_price']:,.2f}")
            print(f"      SL: ${self.current_trade['sl_price']:,.2f}")

    def run(self, check_interval=60):
        """Run paper trading loop"""
        print("="*80)
        print("🚀 LIVE PAPER TRADING - Adaptive 10x Strategy")
        print("="*80)
        print(f"\nStarting balance: ${self.balance:,.2f}")
        print(f"Check interval: {check_interval}s")
        print(f"Strategy: FractalTrendAdaptive (10x leverage)")
        print("\nPress Ctrl+C to stop\n")
        print("="*80)

        try:
            iteration = 0
            while True:
                iteration += 1
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"\n⏰ {now} (Check #{iteration})")

                # Check for entry
                if self.current_trade is None:
                    self.check_entry()

                # Check for exit
                self.check_exit()

                # Status every 5 checks
                if iteration % 5 == 0:
                    self.print_status()

                # Wait
                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n⏹️  Paper trading stopped by user")
            self.print_status()
            self.save_state()
            print(f"\n✅ State saved to {self.log_file}")
            print("\nTo resume: python paper_trading_live.py")


def main():
    trader = LivePaperTrader()
    trader.run(check_interval=60)  # Check every 60 seconds


if __name__ == '__main__':
    main()
