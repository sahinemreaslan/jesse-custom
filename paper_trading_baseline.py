#!/usr/bin/env python3
"""
Paper Trading - BASELINE Strategy (714% ROI)
=============================================

Simple baseline strategy WITHOUT adaptive features
Just the winning core logic that produced 714% ROI
"""

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import numpy as np


class BaselinePaperTrader:
    def __init__(self, csv_path):
        # Load data
        print("Loading historical data...")
        self.df_15m = self.load_csv_data(csv_path)
        self.df_4h = self.resample_to_4h(self.df_15m)

        # BASELINE Strategy Parameters (714% ROI)
        self.leverage = 10
        self.position_size = 0.05  # 5%
        self.tp_percent = 0.007    # 0.7%
        self.sl_percent = 0.0035   # 0.35%
        self.commission = 0.0004   # 0.04%
        self.min_strength = 50

        # Trailing stop
        self.trailing_activation = 0.005  # 0.5%
        self.trailing_distance = 0.002    # 0.2%

        # State
        self.balance = 10000
        self.initial_balance = 10000
        self.peak_balance = 10000
        self.current_trade = None
        self.trades = []

        # Start from ~6 months back
        self.current_index = max(200, len(self.df_15m) - 20000)

        print(f"Data loaded: {len(self.df_15m)} candles")
        print(f"Starting from: {self.df_15m.index[self.current_index]}")
        print(f"Will simulate {len(self.df_15m) - self.current_index} candles")

    def load_csv_data(self, csv_path):
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
        df_4h = df_15m.resample('4h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        return df_4h.dropna()

    def get_recent_data(self):
        start_idx = max(0, self.current_index - 200)
        return self.df_15m.iloc[start_idx:self.current_index]

    def detect_fractal(self, df):
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
        if self.current_index >= len(self.df_15m) - 1:
            return None

        self.current_index += 1

        df_recent = self.get_recent_data()
        current_time = self.df_15m.index[self.current_index]
        df_4h_recent = self.df_4h[self.df_4h.index <= current_time].tail(100)

        if len(df_recent) < 100 or len(df_4h_recent) < 50:
            return None

        if self.current_trade is None:
            return self.check_entry(df_recent, df_4h_recent)
        else:
            return self.check_exit(df_recent)

    def check_entry(self, df_15m, df_4h):
        """BASELINE ENTRY (No adaptive features)"""

        # Rule 1 & 2: Fractal
        pattern, strength = self.detect_fractal(df_15m)

        if pattern not in ['Trending Up', 'Outside Bar']:
            return None

        if strength < self.min_strength:
            return None

        # Rule 3: 4h trend
        df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()

        if df_4h['close'].iloc[-1] <= df_4h['ema_50'].iloc[-1]:
            return None

        # ENTRY!
        entry_price = df_15m['close'].iloc[-1]
        position_value = self.balance * self.position_size * self.leverage
        entry_commission = position_value * self.commission

        self.current_trade = {
            'entry_time': df_15m.index[-1],
            'entry_price': entry_price,
            'position_value': position_value,
            'collateral': self.balance * self.position_size,
            'tp_price': entry_price * (1 + self.tp_percent),
            'sl_price': entry_price * (1 - self.sl_percent),
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

    def check_exit(self, df_15m):
        if self.current_trade is None:
            return None

        current_price = df_15m['close'].iloc[-1]
        high_price = df_15m['high'].iloc[-1]
        low_price = df_15m['low'].iloc[-1]

        # Update highest
        if high_price > self.current_trade['highest_price']:
            self.current_trade['highest_price'] = high_price

        # Trailing stop
        if not self.current_trade['trailing_active']:
            if current_price >= self.current_trade['entry_price'] * (1 + self.trailing_activation):
                self.current_trade['trailing_active'] = True
                self.current_trade['trailing_stop'] = current_price * (1 - self.trailing_distance)

        if self.current_trade['trailing_active']:
            new_trailing = self.current_trade['highest_price'] * (1 - self.trailing_distance)
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
trader = BaselinePaperTrader(csv_path)

# Dash app
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("📊 Paper Trading - BASELINE Strategy (714% ROI)",
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
        interval=2*1000,
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
    signal = trader.step_forward()
    stats = trader.get_stats()

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
        equity_fig.update_layout(title='Equity Curve (Waiting for first trade...)')

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

    # Position
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
    print("🚀 BASELINE PAPER TRADING (714% ROI Strategy)")
    print("="*80)
    print()
    print(f"Strategy: FractalTrend 10x (NO Adaptive Features)")
    print(f"Starting Balance: ${trader.balance:,.2f}")
    print(f"Leverage: {trader.leverage}x")
    print(f"TP: {trader.tp_percent*100}% | SL: {trader.sl_percent*100}%")
    print(f"Position Size: {trader.position_size*100}%")
    print()
    print(f"Dashboard: http://localhost:8050")
    print()
    print("="*80)

    app.run(debug=False, host='0.0.0.0', port=8050)
