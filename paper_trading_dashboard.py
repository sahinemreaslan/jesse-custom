#!/usr/bin/env python3
"""
Paper Trading Dashboard
=======================

Real-time paper trading with live charts and monitoring
Uses Plotly Dash for web-based dashboard
"""

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timedelta
import json
import os


class PaperTradingBot:
    def __init__(self):
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

        # Database
        self.conn = None
        self.connect_db()

        # State file
        self.state_file = 'paper_trading_state.json'
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
        """Load previous state"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
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
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)

    def fetch_recent_candles(self, timeframe='15m', limit=200):
        """Fetch recent candles"""
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

    def get_adaptive_params(self, df_15m, df_4h):
        """Calculate adaptive parameters"""
        # ATR
        atr_current = self.calculate_atr(df_15m, 14)[-1]
        atr_baseline = np.mean(self.calculate_atr(df_15m, 14)[-100:])
        vol_ratio = atr_current / atr_baseline if atr_baseline > 0 else 1.0

        # Adaptive TP/SL
        adaptive_tp = self.base_tp * vol_ratio
        adaptive_sl = self.base_sl * vol_ratio
        adaptive_tp = np.clip(adaptive_tp, 0.004, 0.015)
        adaptive_sl = np.clip(adaptive_sl, 0.002, 0.008)

        # ADX
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
        """Check for entry signal"""
        if self.current_trade is not None:
            return None

        # Fetch data
        df_15m = self.fetch_recent_candles('15m', 200)
        df_4h = self.fetch_recent_candles('4h', 100)

        if len(df_15m) < 100 or len(df_4h) < 50:
            return None

        # 4h trend
        df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()
        if df_4h['close'].iloc[-1] <= df_4h['ema_50'].iloc[-1]:
            return None

        # Fractal
        pattern, strength = self.detect_fractal(df_15m)

        # Adaptive params
        params = self.get_adaptive_params(df_15m, df_4h)

        if params['position_size'] == 0:
            return None

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

            return {
                'type': 'ENTRY',
                'pattern': pattern,
                'strength': strength,
                'price': entry_price,
                'tp': self.current_trade['tp_price'],
                'sl': self.current_trade['sl_price'],
            }

        return None

    def check_exit(self):
        """Check for exit signal"""
        if self.current_trade is None:
            return None

        # Fetch latest
        df_15m = self.fetch_recent_candles('15m', 5)
        if len(df_15m) == 0:
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

            result = {
                'type': 'EXIT',
                'exit_type': exit_type,
                'price': exit_price,
                'pnl': net_pnl,
                'balance': self.balance,
            }

            self.current_trade = None
            self.save_state()

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
            'peak': self.peak_balance,
            'trades': len(self.trades),
            'win_rate': win_rate,
            'has_position': self.current_trade is not None,
        }


# Initialize bot
bot = PaperTradingBot()

# Create Dash app
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("📊 Paper Trading Dashboard - FractalTrend Adaptive 10x",
            style={'textAlign': 'center', 'color': '#2c3e50'}),

    html.Div([
        html.Div([
            html.H3(id='balance', style={'color': '#27ae60'}),
            html.P("Balance")
        ], className='stat-box'),

        html.Div([
            html.H3(id='roi', style={'color': '#3498db'}),
            html.P("ROI")
        ], className='stat-box'),

        html.Div([
            html.H3(id='trades', style={'color': '#e74c3c'}),
            html.P("Trades")
        ], className='stat-box'),

        html.Div([
            html.H3(id='win-rate', style={'color': '#f39c12'}),
            html.P("Win Rate")
        ], className='stat-box'),
    ], style={'display': 'flex', 'justifyContent': 'space-around', 'margin': '20px'}),

    html.Div([
        dcc.Graph(id='equity-curve'),
    ]),

    html.Div([
        dcc.Graph(id='price-chart'),
    ]),

    html.Div(id='current-position', style={'padding': '20px', 'fontSize': '16px'}),

    html.Div(id='recent-trades-table', style={'padding': '20px'}),

    dcc.Interval(
        id='interval-component',
        interval=10*1000,  # Update every 10 seconds
        n_intervals=0
    )
], style={'fontFamily': 'Arial, sans-serif'})


@app.callback(
    [Output('balance', 'children'),
     Output('roi', 'children'),
     Output('trades', 'children'),
     Output('win-rate', 'children'),
     Output('equity-curve', 'figure'),
     Output('price-chart', 'figure'),
     Output('current-position', 'children'),
     Output('recent-trades-table', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    # Check for signals
    entry_signal = bot.check_entry()
    exit_signal = bot.check_exit()

    # Get stats
    stats = bot.get_stats()

    # Fetch current price
    df_15m = bot.fetch_recent_candles('15m', 100)

    # Stats display
    balance_text = f"${stats['balance']:.2f}"
    roi_text = f"{stats['roi']:+.2f}%"
    trades_text = f"{stats['trades']}"
    wr_text = f"{stats['win_rate']:.1f}%"

    # Equity curve
    if len(bot.trades) > 0:
        trades_df = pd.DataFrame(bot.trades)
        trades_df['timestamp'] = pd.to_datetime(trades_df['exit_time'])
        equity_trace = go.Scatter(
            x=trades_df['timestamp'],
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
    candlestick = go.Candlestick(
        x=df_15m.index,
        open=df_15m['open'],
        high=df_15m['high'],
        low=df_15m['low'],
        close=df_15m['close'],
        name='BTC-USDT'
    )

    price_fig = go.Figure(data=[candlestick])

    # Add entry/exit markers
    if len(bot.trades) > 0:
        recent_trades = bot.trades[-10:]
        entry_times = [pd.to_datetime(t['entry_time']) for t in recent_trades]
        entry_prices = [t['entry_price'] for t in recent_trades]
        exit_times = [pd.to_datetime(t['exit_time']) for t in recent_trades]
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
    if bot.current_trade:
        current_price = df_15m['close'].iloc[-1]
        unrealized = ((current_price / bot.current_trade['entry_price']) - 1) * bot.leverage * bot.current_trade['collateral']

        position_text = html.Div([
            html.H3("🔄 OPEN POSITION", style={'color': '#3498db'}),
            html.P(f"Pattern: {bot.current_trade['pattern']} (Strength: {bot.current_trade['strength']})"),
            html.P(f"Entry: ${bot.current_trade['entry_price']:,.2f}"),
            html.P(f"Current: ${current_price:,.2f}"),
            html.P(f"TP: ${bot.current_trade['tp_price']:,.2f}"),
            html.P(f"SL: ${bot.current_trade['sl_price']:,.2f}"),
            html.P(f"Unrealized PnL: ${unrealized:+,.2f}",
                   style={'color': 'green' if unrealized > 0 else 'red', 'fontSize': '18px', 'fontWeight': 'bold'}),
        ])
    else:
        position_text = html.Div([
            html.H3("⏸️ NO POSITION", style={'color': '#95a5a6'}),
            html.P("Waiting for entry signal..."),
        ])

    # Recent trades table
    if len(bot.trades) > 0:
        recent_trades = bot.trades[-5:]
        table_header = [
            html.Thead(html.Tr([
                html.Th("Exit Time"),
                html.Th("Pattern"),
                html.Th("Entry"),
                html.Th("Exit"),
                html.Th("Type"),
                html.Th("PnL"),
            ]))
        ]

        rows = []
        for trade in reversed(recent_trades):
            rows.append(html.Tr([
                html.Td(trade['exit_time'][:19]),
                html.Td(trade['pattern']),
                html.Td(f"${trade['entry_price']:,.0f}"),
                html.Td(f"${trade['exit_price']:,.0f}"),
                html.Td(trade['exit_type']),
                html.Td(f"${trade['pnl']:+,.2f}",
                       style={'color': 'green' if trade['pnl'] > 0 else 'red'}),
            ]))

        table_body = [html.Tbody(rows)]
        trades_table = html.Table(table_header + table_body,
                                  style={'width': '100%', 'borderCollapse': 'collapse', 'border': '1px solid #ddd'})
    else:
        trades_table = html.P("No trades yet")

    return balance_text, roi_text, trades_text, wr_text, equity_fig, price_fig, position_text, trades_table


if __name__ == '__main__':
    print("="*80)
    print("🚀 STARTING PAPER TRADING DASHBOARD")
    print("="*80)
    print()
    print(f"Strategy: FractalTrend Adaptive 10x")
    print(f"Starting Balance: ${bot.balance:,.2f}")
    print(f"Leverage: {bot.leverage}x")
    print()
    print(f"Dashboard running at: http://localhost:8050")
    print()
    print("Press Ctrl+C to stop")
    print("="*80)
    print()

    app.run_server(debug=False, host='0.0.0.0', port=8050)
