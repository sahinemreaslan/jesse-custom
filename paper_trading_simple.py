#!/usr/bin/env python3
"""
Simple Paper Trading Simulator
================================

Uses CSV data for simulation (no PostgreSQL needed)
Simulates forward from last known date
"""

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os


class SimplePaperTrader:
    def __init__(self, csv_path):
        # Load historical data
        print("Loading historical data...")
        self.df_15m = self.load_csv_data(csv_path)
        self.df_4h = self.resample_to_4h(self.df_15m)

        # Strategy config
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

        # Simulation state
        # Start from ~6 months back to ensure we have active trading signals
        self.current_index = max(200, len(self.df_15m) - 20000)

        print(f"Data loaded: {len(self.df_15m)} candles")
        print(f"Starting from: {self.df_15m.index[self.current_index]}")
        print(f"Will simulate {len(self.df_15m) - self.current_index} candles forward")

    def load_csv_data(self, csv_path):
        """Load CSV data"""
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

    def resample_to_4h(self, df_15m):
        """Resample to 4h"""
        df_4h = df_15m.resample('4h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        return df_4h.dropna()

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

    def get_recent_data(self):
        """Get recent 200 candles from current position"""
        start_idx = max(0, self.current_index - 200)
        return self.df_15m.iloc[start_idx:self.current_index]

    def detect_fractal(self, df):
        """Detect fractal on latest candles"""
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

    def step_forward(self):
        """Advance one candle and check signals"""
        if self.current_index >= len(self.df_15m) - 1:
            return None  # End of data

        self.current_index += 1

        # Get recent data
        df_recent = self.get_recent_data()

        # Get 4h data
        current_time = self.df_15m.index[self.current_index]
        df_4h_recent = self.df_4h[self.df_4h.index <= current_time].tail(100)

        if len(df_recent) < 100 or len(df_4h_recent) < 50:
            return None

        # Check entry
        if self.current_trade is None:
            return self.check_entry(df_recent, df_4h_recent)
        else:
            return self.check_exit(df_recent)

    def check_entry(self, df_15m, df_4h):
        """Check for entry signal"""
        # 4h trend
        df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()
        if df_4h['close'].iloc[-1] <= df_4h['ema_50'].iloc[-1]:
            return None

        # Fractal
        pattern, strength = self.detect_fractal(df_15m)

        # ATR & ADX
        atr_current = self.calculate_atr(df_15m, 14)[-1]
        atr_baseline = np.mean(self.calculate_atr(df_15m, 14)[-100:])
        vol_ratio = atr_current / atr_baseline if atr_baseline > 0 else 1.0

        adaptive_tp = self.base_tp * vol_ratio
        adaptive_sl = self.base_sl * vol_ratio
        adaptive_tp = np.clip(adaptive_tp, 0.004, 0.015)
        adaptive_sl = np.clip(adaptive_sl, 0.002, 0.008)

        adx = self.calculate_adx(df_15m, 14)[-1]
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

        # Drawdown
        dd = (self.balance - self.peak_balance) / self.peak_balance if self.peak_balance > 0 else 0
        if dd < -0.05:
            return None

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
        else:
            dd_multiplier = 0.3

        position_size = self.base_position_size * dd_multiplier

        if len(self.recent_trades) >= 10:
            win_rate = sum([1 for t in self.recent_trades[-20:] if t > 0]) / len(self.recent_trades[-20:])
            if win_rate > 0.6:
                position_size *= 1.1
            elif win_rate < 0.4:
                position_size *= 0.9

        position_size = np.clip(position_size, 0.01, 0.08)

        # Entry check
        if (pattern in ['Trending Up', 'Outside Bar'] and
            strength >= min_strength):

            entry_price = df_15m['close'].iloc[-1]
            position_value = self.balance * position_size * self.leverage
            entry_commission = position_value * self.commission

            self.current_trade = {
                'entry_time': df_15m.index[-1],
                'entry_price': entry_price,
                'position_value': position_value,
                'collateral': self.balance * position_size,
                'tp_price': entry_price * (1 + adaptive_tp),
                'sl_price': entry_price * (1 - adaptive_sl),
                'highest_price': entry_price,
                'trailing_active': False,
                'trailing_stop': None,
                'entry_commission': entry_commission,
                'pattern': pattern,
                'strength': strength,
            }

            return {
                'type': 'ENTRY',
                'pattern': pattern,
                'strength': strength,
                'price': entry_price,
            }

        return None

    def check_exit(self, df_15m):
        """Check for exit signal"""
        if self.current_trade is None:
            return None

        current_price = df_15m['close'].iloc[-1]
        high_price = df_15m['high'].iloc[-1]
        low_price = df_15m['low'].iloc[-1]

        # Update highest
        if high_price > self.current_trade['highest_price']:
            self.current_trade['highest_price'] = high_price

        # Trailing
        if not self.current_trade['trailing_active']:
            if current_price >= self.current_trade['entry_price'] * 1.005:
                self.current_trade['trailing_active'] = True
                self.current_trade['trailing_stop'] = current_price * 0.998

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

            if self.balance > self.peak_balance:
                self.peak_balance = self.balance

            trade_record = {
                'entry_time': self.current_trade['entry_time'],
                'exit_time': df_15m.index[-1],
                'entry_price': self.current_trade['entry_price'],
                'exit_price': exit_price,
                'exit_type': exit_type,
                'pnl': net_pnl,
                'balance_after': self.balance,
                'pattern': self.current_trade['pattern'],
            }
            self.trades.append(trade_record)

            result = {
                'type': 'EXIT',
                'exit_type': exit_type,
                'price': exit_price,
                'pnl': net_pnl,
            }

            self.current_trade = None
            return result

        return None

    def get_stats(self):
        """Get current statistics"""
        roi = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        dd = ((self.balance - self.peak_balance) / self.peak_balance) * 100 if self.peak_balance > 0 else 0

        win_count = sum([1 for t in self.trades if t['pnl'] > 0])
        win_rate = (win_count / len(self.trades) * 100) if len(self.trades) > 0 else 0

        return {
            'balance': self.balance,
            'roi': roi,
            'dd': dd,
            'trades': len(self.trades),
            'win_rate': win_rate,
            'has_position': self.current_trade is not None,
            'current_time': self.df_15m.index[self.current_index] if self.current_index < len(self.df_15m) else None,
        }


# Initialize
csv_path = '/home/voidstring/Desktop/jesse_real/btc_15m_data_2018_to_2025.csv'
trader = SimplePaperTrader(csv_path)

# Create Dash app
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("📊 Simple Paper Trading Simulator - FractalTrend 10x",
            style={'textAlign': 'center', 'color': '#2c3e50'}),

    html.Div([
        html.Div([
            html.H3(id='balance', style={'color': '#27ae60'}),
            html.P("Balance")
        ], style={'flex': 1, 'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'margin': '10px'}),

        html.Div([
            html.H3(id='roi', style={'color': '#3498db'}),
            html.P("ROI")
        ], style={'flex': 1, 'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'margin': '10px'}),

        html.Div([
            html.H3(id='trades', style={'color': '#e74c3c'}),
            html.P("Trades")
        ], style={'flex': 1, 'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'margin': '10px'}),

        html.Div([
            html.H3(id='win-rate', style={'color': '#f39c12'}),
            html.P("Win Rate")
        ], style={'flex': 1, 'textAlign': 'center', 'padding': '20px', 'border': '1px solid #ddd', 'margin': '10px'}),
    ], style={'display': 'flex', 'justifyContent': 'space-around'}),

    html.Div(id='current-time', style={'textAlign': 'center', 'fontSize': '18px', 'padding': '10px'}),

    html.Div([
        dcc.Graph(id='equity-curve'),
    ]),

    html.Div([
        dcc.Graph(id='price-chart'),
    ]),

    html.Div(id='current-position', style={'padding': '20px', 'fontSize': '16px'}),

    dcc.Interval(
        id='interval-component',
        interval=2*1000,  # Update every 2 seconds (fast simulation)
        n_intervals=0
    )
], style={'fontFamily': 'Arial, sans-serif'})


@app.callback(
    [Output('balance', 'children'),
     Output('roi', 'children'),
     Output('trades', 'children'),
     Output('win-rate', 'children'),
     Output('current-time', 'children'),
     Output('equity-curve', 'figure'),
     Output('price-chart', 'figure'),
     Output('current-position', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    # Step forward in simulation
    signal = trader.step_forward()

    # Get stats
    stats = trader.get_stats()

    # Stats display
    balance_text = f"${stats['balance']:.2f}"
    roi_text = f"{stats['roi']:+.2f}%"
    trades_text = f"{stats['trades']}"
    wr_text = f"{stats['win_rate']:.1f}%"
    time_text = f"Current Time: {stats['current_time']}" if stats['current_time'] else "Simulation Complete"

    # Equity curve
    if len(trader.trades) > 0:
        trades_df = pd.DataFrame(trader.trades)
        equity_trace = go.Scatter(
            x=trades_df['exit_time'],
            y=trades_df['balance_after'],
            mode='lines+markers',
            name='Balance',
            line=dict(color='#27ae60', width=2)
        )
        equity_fig = go.Figure(data=[equity_trace])
        equity_fig.update_layout(
            title='Equity Curve',
            xaxis_title='Time',
            yaxis_title='Balance ($)',
            hovermode='x unified'
        )
    else:
        equity_fig = go.Figure()
        equity_fig.update_layout(title='Equity Curve (No trades yet)')

    # Price chart
    df_display = trader.get_recent_data().tail(100)
    candlestick = go.Candlestick(
        x=df_display.index,
        open=df_display['open'],
        high=df_display['high'],
        low=df_display['low'],
        close=df_display['close'],
        name='BTC-USDT'
    )

    price_fig = go.Figure(data=[candlestick])

    # Add recent trades
    if len(trader.trades) > 0:
        recent_trades = trader.trades[-10:]
        entry_times = [t['entry_time'] for t in recent_trades]
        entry_prices = [t['entry_price'] for t in recent_trades]
        exit_times = [t['exit_time'] for t in recent_trades]
        exit_prices = [t['exit_price'] for t in recent_trades]

        price_fig.add_trace(go.Scatter(
            x=entry_times, y=entry_prices,
            mode='markers',
            name='Entry',
            marker=dict(color='green', size=10, symbol='triangle-up')
        ))

        price_fig.add_trace(go.Scatter(
            x=exit_times, y=exit_prices,
            mode='markers',
            name='Exit',
            marker=dict(color='red', size=10, symbol='triangle-down')
        ))

    price_fig.update_layout(
        title='BTC-USDT 15m Chart',
        xaxis_title='Time',
        yaxis_title='Price ($)',
        xaxis_rangeslider_visible=False
    )

    # Current position
    if trader.current_trade:
        current_price = df_display['close'].iloc[-1]
        unrealized = ((current_price / trader.current_trade['entry_price']) - 1) * trader.leverage * trader.current_trade['collateral']

        position_text = html.Div([
            html.H3("🔄 OPEN POSITION", style={'color': '#3498db'}),
            html.P(f"Pattern: {trader.current_trade['pattern']} (Strength: {trader.current_trade['strength']})"),
            html.P(f"Entry: ${trader.current_trade['entry_price']:,.2f}"),
            html.P(f"Current: ${current_price:,.2f}"),
            html.P(f"TP: ${trader.current_trade['tp_price']:,.2f}"),
            html.P(f"SL: ${trader.current_trade['sl_price']:,.2f}"),
            html.P(f"Unrealized PnL: ${unrealized:+,.2f}",
                   style={'color': 'green' if unrealized > 0 else 'red', 'fontSize': '18px', 'fontWeight': 'bold'}),
        ])
    else:
        position_text = html.Div([
            html.H3("⏸️ NO POSITION", style={'color': '#95a5a6'}),
            html.P("Waiting for entry signal..."),
        ])

    return balance_text, roi_text, trades_text, wr_text, time_text, equity_fig, price_fig, position_text


if __name__ == '__main__':
    print("="*80)
    print("🚀 STARTING SIMPLE PAPER TRADING SIMULATOR")
    print("="*80)
    print()
    print(f"Strategy: FractalTrend Adaptive 10x")
    print(f"Starting Balance: ${trader.balance:,.2f}")
    print(f"Leverage: {trader.leverage}x")
    print(f"Simulation Speed: 1 candle every 2 seconds")
    print()
    print(f"Dashboard running at: http://localhost:8050")
    print()
    print("Press Ctrl+C to stop")
    print("="*80)
    print()

    app.run(debug=False, host='0.0.0.0', port=8050)
