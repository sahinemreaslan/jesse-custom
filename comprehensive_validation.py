#!/usr/bin/env python3
"""
Comprehensive Strategy Validation Suite
========================================

1. Walk-Forward Validation
2. Long Period Backtest (2023-2024)
3. Monte Carlo Simulation
4. High Risk Profile Testing (10x, 15x, 20x)
"""

import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import warnings
import random
warnings.filterwarnings('ignore')


# ====================================================================================================
# KONFİGÜRASYONLAR
# ====================================================================================================

# Base strategy (4h Trend + 50 Strength)
BASE_STRATEGY = {
    'min_fractal_strength': 50,
    'trend_timeframe': '4h',
    'trend_ema_period': 50,
    'fractal_patterns': ['Trending Up', 'Outside Bar'],
}

# Test edilecek kaldıraç konfigürasyonları
TEST_CONFIGS = [
    {
        'name': '5x Balanced (Winner)',
        'leverage': 5,
        'position_size': 0.06,
        'tp_percent': 0.008,
        'sl_percent': 0.004,
        'trailing_activation': 0.006,
        'trailing_distance': 0.002,
    },
    {
        'name': '10x Moderate',
        'leverage': 10,
        'position_size': 0.04,
        'tp_percent': 0.006,
        'sl_percent': 0.003,
        'trailing_activation': 0.004,
        'trailing_distance': 0.0015,
    },
    {
        'name': '10x Aggressive',
        'leverage': 10,
        'position_size': 0.05,  # Daha büyük pozisyon
        'tp_percent': 0.007,
        'sl_percent': 0.0035,
        'trailing_activation': 0.005,
        'trailing_distance': 0.002,
    },
    {
        'name': '15x High Risk',
        'leverage': 15,
        'position_size': 0.03,
        'tp_percent': 0.005,
        'sl_percent': 0.0025,
        'trailing_activation': 0.003,
        'trailing_distance': 0.001,
    },
    {
        'name': '20x Extreme',
        'leverage': 20,
        'position_size': 0.025,
        'tp_percent': 0.004,
        'sl_percent': 0.002,
        'trailing_activation': 0.003,
        'trailing_distance': 0.001,
    },
]


# ====================================================================================================
# VERİ YÜKLEME
# ====================================================================================================

class DataLoader:
    def __init__(self):
        self.conn = psycopg2.connect(
            host='127.0.0.1',
            database='jesse_db',
            user='voidstring',
            password=''
        )

    def load_data(self, start_date: str, end_date: str, trend_tf: str = '4h') -> pd.DataFrame:
        """15m + trend timeframe verilerini yükle"""

        start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
        end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)

        # 15m veri
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

        df_15m = pd.read_sql_query(query_15m, self.conn)
        df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        df_15m.set_index('timestamp', inplace=True)

        # Trend timeframe veri
        query_trend = f"""
            SELECT timestamp, open, high, low, close, volume
            FROM candle
            WHERE symbol = 'BTC-USDT'
            AND exchange = 'Binance Futures'
            AND timeframe = '{trend_tf}'
            AND timestamp >= {start_ts}
            AND timestamp <= {end_ts}
            ORDER BY timestamp
        """

        df_trend = pd.read_sql_query(query_trend, self.conn)
        df_trend['timestamp'] = pd.to_datetime(df_trend['timestamp'], unit='ms')
        df_trend.set_index('timestamp', inplace=True)

        # EMA hesapla
        df_trend['ema_50'] = df_trend['close'].ewm(span=50, adjust=False).mean()

        # Merge
        for col in ['close', 'ema_50']:
            df_15m[f'{trend_tf}_{col}'] = df_15m.index.map(
                lambda dt: df_trend[df_trend.index <= dt][col].iloc[-1]
                if len(df_trend[df_trend.index <= dt]) > 0 else np.nan
            )

        # Fraktal analiz
        df_15m = self._add_fractal_analysis(df_15m)

        # NaN temizle
        df_15m.dropna(inplace=True)

        return df_15m

    def _add_fractal_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        df['fractal_pattern'] = None
        df['fractal_strength'] = 0

        for i in range(2, len(df) - 2):
            current = df.iloc[i]
            prev2 = df.iloc[i-2]
            prev1 = df.iloc[i-1]

            # Trending Up
            if (current['close'] > prev1['close'] > prev2['close'] and
                current['high'] > prev1['high'] > prev2['high']):
                body = abs(current['close'] - current['open'])
                range_val = current['high'] - current['low']
                strength = int((body / range_val) * 100) if range_val > 0 else 0
                df.iloc[i, df.columns.get_loc('fractal_pattern')] = 'Trending Up'
                df.iloc[i, df.columns.get_loc('fractal_strength')] = strength

            # Outside Bar
            elif (current['high'] > prev1['high'] and current['low'] < prev1['low'] and
                  current['close'] > current['open']):
                body = abs(current['close'] - current['open'])
                range_val = current['high'] - current['low']
                strength = int((body / range_val) * 100) if range_val > 0 else 0
                df.iloc[i, df.columns.get_loc('fractal_pattern')] = 'Outside Bar'
                df.iloc[i, df.columns.get_loc('fractal_strength')] = strength

        return df


# ====================================================================================================
# BACKTEST ENGINE
# ====================================================================================================

class Backtester:
    def __init__(self, config: Dict, initial_capital: float = 10000):
        self.config = config
        self.initial_capital = initial_capital
        self.commission_rate = 0.0004
        self.trades = []

    def check_entry_signal(self, row) -> bool:
        if row['fractal_pattern'] not in BASE_STRATEGY['fractal_patterns']:
            return False
        if row['fractal_strength'] < BASE_STRATEGY['min_fractal_strength']:
            return False
        trend_tf = BASE_STRATEGY['trend_timeframe']
        if row[f'{trend_tf}_close'] <= row[f'{trend_tf}_ema_50']:
            return False
        return True

    def calculate_liquidation_price(self, entry_price: float, leverage: int) -> float:
        return entry_price * (1 - 0.9 / leverage)

    def run_backtest(self, df: pd.DataFrame) -> Dict:
        self.trades = []
        current_trade = None
        balance = self.initial_capital
        leverage = self.config['leverage']
        peak_balance = balance

        for idx, row in df.iterrows():
            if current_trade is None:
                if self.check_entry_signal(row):
                    position_value = balance * self.config['position_size'] * leverage
                    commission = position_value * self.commission_rate
                    liquidation_price = self.calculate_liquidation_price(row['close'], leverage)

                    current_trade = {
                        'entry_time': idx,
                        'entry_price': row['close'],
                        'position_value': position_value,
                        'collateral': balance * self.config['position_size'],
                        'leverage': leverage,
                        'tp_price': row['close'] * (1 + self.config['tp_percent']),
                        'sl_price': row['close'] * (1 - self.config['sl_percent']),
                        'liquidation_price': liquidation_price,
                        'trailing_active': False,
                        'trailing_stop': None,
                        'highest_price': row['close'],
                        'entry_commission': commission,
                    }
            else:
                current_price = row['close']
                high_price = row['high']
                low_price = row['low']

                if high_price > current_trade['highest_price']:
                    current_trade['highest_price'] = high_price

                if not current_trade['trailing_active']:
                    activation_price = current_trade['entry_price'] * (1 + self.config['trailing_activation'])
                    if current_price >= activation_price:
                        current_trade['trailing_active'] = True
                        current_trade['trailing_stop'] = current_price * (1 - self.config['trailing_distance'])

                if current_trade['trailing_active']:
                    new_trailing = current_trade['highest_price'] * (1 - self.config['trailing_distance'])
                    if new_trailing > current_trade['trailing_stop']:
                        current_trade['trailing_stop'] = new_trailing

                exit_type = None
                exit_price = None

                if low_price <= current_trade['liquidation_price']:
                    exit_type = 'Liquidation'
                    exit_price = current_trade['liquidation_price']
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
                    exit_commission = current_trade['position_value'] * self.commission_rate
                    price_change_pct = (exit_price / current_trade['entry_price']) - 1
                    leveraged_pnl_pct = price_change_pct * leverage
                    gross_pnl = current_trade['collateral'] * leveraged_pnl_pct
                    net_pnl = gross_pnl - current_trade['entry_commission'] - exit_commission

                    if exit_type == 'Liquidation':
                        net_pnl = -current_trade['collateral']

                    balance += net_pnl

                    if balance > peak_balance:
                        peak_balance = balance

                    self.trades.append({
                        'entry_time': current_trade['entry_time'],
                        'exit_time': idx,
                        'entry_price': current_trade['entry_price'],
                        'exit_price': exit_price,
                        'exit_type': exit_type,
                        'pnl': net_pnl,
                        'pnl_pct': leveraged_pnl_pct,
                        'leverage': leverage,
                        'balance': balance,
                    })

                    current_trade = None

                    if balance <= 0:
                        break

        # Calculate metrics
        final_balance = balance
        roi = ((final_balance - self.initial_capital) / self.initial_capital) * 100

        trades_df = pd.DataFrame(self.trades)

        if len(trades_df) > 0:
            wins = trades_df[trades_df['pnl'] > 0]
            losses = trades_df[trades_df['pnl'] <= 0]
            win_rate = len(wins) / len(trades_df) * 100
            total_profit = wins['pnl'].sum() if len(wins) > 0 else 0
            total_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1
            profit_factor = total_profit / total_loss if total_loss > 0 else 0
            exit_counts = trades_df['exit_type'].value_counts().to_dict()

            # Drawdown calculation
            trades_df['cumulative_balance'] = trades_df['balance']
            trades_df['peak_balance'] = trades_df['cumulative_balance'].expanding().max()
            trades_df['drawdown'] = (trades_df['cumulative_balance'] - trades_df['peak_balance']) / trades_df['peak_balance'] * 100
            max_drawdown = trades_df['drawdown'].min()

            avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
            avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
            liquidations = len(trades_df[trades_df['exit_type'] == 'Liquidation'])
        else:
            win_rate = 0
            profit_factor = 0
            exit_counts = {}
            max_drawdown = 0
            avg_win = 0
            avg_loss = 0
            liquidations = 0

        return {
            'roi': roi,
            'final_balance': final_balance,
            'num_trades': len(trades_df),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'exit_counts': exit_counts,
            'max_drawdown': max_drawdown,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'liquidations': liquidations,
            'trades_df': trades_df,
        }


# ====================================================================================================
# 1. WALK-FORWARD VALIDATION
# ====================================================================================================

def walk_forward_validation(config: Dict, loader: DataLoader):
    print("\n" + "="*100)
    print(f"📊 WALK-FORWARD VALIDATION: {config['name']}")
    print("="*100)

    quarters = [
        ('2024-01-01', '2024-03-31', 'Q1 2024'),
        ('2024-04-01', '2024-06-30', 'Q2 2024'),
        ('2024-07-01', '2024-09-30', 'Q3 2024'),
        ('2024-10-01', '2024-10-31', 'Q4 2024 (partial)'),
    ]

    results = []

    for i, (start, end, label) in enumerate(quarters):
        df = loader.load_data(start, end, BASE_STRATEGY['trend_timeframe'])
        backtester = Backtester(config)
        result = backtester.run_backtest(df)

        results.append({
            'quarter': label,
            'roi': result['roi'],
            'trades': result['num_trades'],
            'win_rate': result['win_rate'],
            'pf': result['profit_factor'],
            'max_dd': result['max_drawdown'],
            'liquidations': result['liquidations'],
        })

        print(f"\n{label}: ROI {result['roi']:>7.2f}%, Trades {result['num_trades']:>3}, WR {result['win_rate']:>5.1f}%, PF {result['profit_factor']:.2f}, MaxDD {result['max_drawdown']:>6.2f}%", end="")
        if result['liquidations'] > 0:
            print(f" ⚠️  Liq: {result['liquidations']}")
        else:
            print()

    results_df = pd.DataFrame(results)
    avg_roi = results_df['roi'].mean()
    std_roi = results_df['roi'].std()
    consistency = "✅ Tutarlı" if std_roi < 10 else "❌ Tutarsız"

    print(f"\n{'─'*100}")
    print(f"Ortalama ROI: {avg_roi:.2f}%")
    print(f"Std Dev: {std_roi:.2f}%")
    print(f"Tutarlılık: {consistency}")

    return results_df


# ====================================================================================================
# 2. LONG PERIOD BACKTEST
# ====================================================================================================

def long_period_backtest(config: Dict, loader: DataLoader):
    print("\n" + "="*100)
    print(f"📈 UZUN PERİYOT BACKTEST (2023-2024): {config['name']}")
    print("="*100)

    df = loader.load_data('2023-01-01', '2024-10-31', BASE_STRATEGY['trend_timeframe'])
    print(f"Veri: {len(df)} mum (2023-01-01 → 2024-10-31)")

    backtester = Backtester(config)
    result = backtester.run_backtest(df)

    print(f"\n📊 SONUÇLAR:")
    print(f"  ROI: {result['roi']:.2f}%")
    print(f"  Final Balance: ${result['final_balance']:.2f}")
    print(f"  Trades: {result['num_trades']}")
    print(f"  Win Rate: {result['win_rate']:.1f}%")
    print(f"  Profit Factor: {result['profit_factor']:.2f}")
    print(f"  Max Drawdown: {result['max_drawdown']:.2f}%")
    print(f"  Avg Win: ${result['avg_win']:.2f}")
    print(f"  Avg Loss: ${result['avg_loss']:.2f}")

    if result['liquidations'] > 0:
        print(f"  ⚠️  Liquidations: {result['liquidations']}")

    # Yıllık ROI extrapolate
    months = 22  # Jan 2023 - Oct 2024
    annual_roi = (result['roi'] / months) * 12
    print(f"\n  Yıllık ROI (extrapolate): ~{annual_roi:.1f}%")

    return result


# ====================================================================================================
# 3. MONTE CARLO SIMULATION
# ====================================================================================================

def monte_carlo_simulation(trades_df: pd.DataFrame, config_name: str, num_simulations: int = 1000):
    print("\n" + "="*100)
    print(f"🎲 MONTE CARLO SIMULATION: {config_name}")
    print("="*100)
    print(f"Simülasyon Sayısı: {num_simulations}")

    if len(trades_df) == 0:
        print("❌ Trade yok, simülasyon yapılamıyor")
        return None

    trade_returns = trades_df['pnl'].values
    initial_capital = 10000

    simulation_results = []

    for _ in range(num_simulations):
        # Random shuffle trades
        shuffled_returns = np.random.choice(trade_returns, size=len(trade_returns), replace=True)

        balance = initial_capital
        peak = balance
        max_dd = 0

        for ret in shuffled_returns:
            balance += ret
            if balance > peak:
                peak = balance
            dd = ((balance - peak) / peak) * 100
            if dd < max_dd:
                max_dd = dd

        final_roi = ((balance - initial_capital) / initial_capital) * 100
        simulation_results.append({
            'final_balance': balance,
            'roi': final_roi,
            'max_dd': max_dd,
        })

    sim_df = pd.DataFrame(simulation_results)

    print(f"\n📊 MONTE CARLO SONUÇLARI:")
    print(f"\nROI İstatistikleri:")
    print(f"  Ortalama: {sim_df['roi'].mean():.2f}%")
    print(f"  Median: {sim_df['roi'].median():.2f}%")
    print(f"  En İyi: {sim_df['roi'].max():.2f}%")
    print(f"  En Kötü: {sim_df['roi'].min():.2f}%")
    print(f"  Std Dev: {sim_df['roi'].std():.2f}%")

    print(f"\nMax Drawdown İstatistikleri:")
    print(f"  Ortalama: {sim_df['max_dd'].mean():.2f}%")
    print(f"  Median: {sim_df['max_dd'].median():.2f}%")
    print(f"  En İyi (düşük DD): {sim_df['max_dd'].max():.2f}%")
    print(f"  En Kötü (yüksek DD): {sim_df['max_dd'].min():.2f}%")

    print(f"\nRisk Metrikleri:")
    positive_roi_pct = (len(sim_df[sim_df['roi'] > 0]) / len(sim_df)) * 100
    print(f"  Pozitif ROI Olasılığı: {positive_roi_pct:.1f}%")

    percentiles = [5, 25, 50, 75, 95]
    print(f"\n  ROI Yüzdelik Dilimleri:")
    for p in percentiles:
        val = np.percentile(sim_df['roi'], p)
        print(f"    {p}th: {val:.2f}%")

    return sim_df


# ====================================================================================================
# MAIN
# ====================================================================================================

def main():
    print("="*100)
    print("COMPREHENSIVE VALIDATION SUITE")
    print("="*100)
    print("\n1. Walk-Forward Validation")
    print("2. Long Period Backtest (2023-2024)")
    print("3. Monte Carlo Simulation")
    print("4. High Risk Profile Testing")
    print()

    loader = DataLoader()

    # Test her konfigürasyon için
    all_results = []

    for config in TEST_CONFIGS:
        print("\n" + "█"*100)
        print(f"█  TEST: {config['name']} (Leverage: {config['leverage']}x)")
        print("█"*100)

        # 1. Walk-Forward Validation
        wfv_results = walk_forward_validation(config, loader)

        # 2. Long Period Backtest
        long_result = long_period_backtest(config, loader)

        # 3. Monte Carlo Simulation
        if len(long_result['trades_df']) > 0:
            mc_results = monte_carlo_simulation(long_result['trades_df'], config['name'])
        else:
            mc_results = None

        all_results.append({
            'name': config['name'],
            'leverage': config['leverage'],
            'wfv_avg_roi': wfv_results['roi'].mean(),
            'wfv_std': wfv_results['roi'].std(),
            'long_roi': long_result['roi'],
            'long_max_dd': long_result['max_drawdown'],
            'long_pf': long_result['profit_factor'],
            'long_liquidations': long_result['liquidations'],
            'mc_median_roi': mc_results['roi'].median() if mc_results is not None else 0,
            'mc_worst_roi': mc_results['roi'].min() if mc_results is not None else 0,
            'mc_worst_dd': mc_results['max_dd'].min() if mc_results is not None else 0,
        })

    # Final comparison
    print("\n" + "="*100)
    print("🏆 FINAL KARŞILAŞTIRMA")
    print("="*100)

    results_df = pd.DataFrame(all_results)
    results_df = results_df.sort_values('long_roi', ascending=False)

    print("\nSıralama (Long Period ROI'ye göre):\n")
    print(f"{'Rank':<5} {'Konfigürasyon':<25} {'Lev':<5} {'LongROI':<10} {'MaxDD':<10} {'PF':<8} {'WFV_Avg':<10} {'MC_Worst':<10} {'Liq':<5}")
    print("─"*100)

    for idx, row in results_df.iterrows():
        rank = results_df.index.get_loc(idx) + 1
        liq_mark = "⚠️ " if row['long_liquidations'] > 0 else "✅"
        print(f"{rank:<5} {row['name']:<25} {row['leverage']:<5}x {row['long_roi']:>8.2f}% {row['long_max_dd']:>8.2f}% {row['long_pf']:>6.2f} {row['wfv_avg_roi']:>8.2f}% {row['mc_worst_roi']:>8.2f}% {liq_mark}")

    # Winner
    best = results_df.iloc[0]
    print("\n" + "="*100)
    print("🏆 KAZANAN KONFİGÜRASYON")
    print("="*100)
    print(f"\n{best['name']} ({best['leverage']}x)")
    print(f"  Long Period ROI: {best['long_roi']:.2f}%")
    print(f"  Max Drawdown: {best['long_max_dd']:.2f}%")
    print(f"  Profit Factor: {best['long_pf']:.2f}")
    print(f"  WFV Ortalama: {best['wfv_avg_roi']:.2f}%")
    print(f"  Monte Carlo En Kötü: {best['mc_worst_roi']:.2f}%")
    print(f"  Monte Carlo En Kötü DD: {best['mc_worst_dd']:.2f}%")

    if best['long_liquidations'] == 0:
        print(f"\n✅ Liquidation yok - Güvenli!")
    else:
        print(f"\n⚠️  {best['long_liquidations']} Liquidation - Dikkatli ol!")

    print("\n" + "="*100)
    print("✅ COMPREHENSIVE VALIDATION TAMAMLANDI")
    print("="*100)


if __name__ == '__main__':
    main()
