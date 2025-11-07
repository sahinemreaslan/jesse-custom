#!/usr/bin/env python3
"""
Kaldıraçlı Fraktal Strateji Optimizasyonu
==========================================

Kazanan stratejiyi (4h Trend + 50 Strength) kaldıraçlı versiyonuyla test eder.

Farklı kaldıraç seviyeleri:
- 2x, 3x, 5x, 10x

Her kaldıraç seviyesi için risk-adjusted TP/SL
"""

import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


# ====================================================================================================
# KALDIRAÇ KONFİGÜRASYONLARI
# ====================================================================================================

LEVERAGE_CONFIGS = [
    {
        'name': 'No Leverage (Baseline)',
        'leverage': 1,
        'position_size': 0.10,
        'tp_percent': 0.015,  # 1.5%
        'sl_percent': 0.008,  # 0.8%
        'trailing_activation': 0.010,  # 1.0%
        'trailing_distance': 0.004,    # 0.4%
    },
    {
        'name': 'Conservative 2x',
        'leverage': 2,
        'position_size': 0.10,  # 10% capital * 2x = 20% exposure
        'tp_percent': 0.012,  # 1.2% (biraz daha kolay TP)
        'sl_percent': 0.006,  # 0.6% (daha sıkı SL)
        'trailing_activation': 0.008,  # 0.8%
        'trailing_distance': 0.003,    # 0.3%
    },
    {
        'name': 'Moderate 3x',
        'leverage': 3,
        'position_size': 0.08,  # 8% capital * 3x = 24% exposure
        'tp_percent': 0.010,  # 1.0%
        'sl_percent': 0.005,  # 0.5%
        'trailing_activation': 0.007,  # 0.7%
        'trailing_distance': 0.0025,   # 0.25%
    },
    {
        'name': 'Aggressive 5x',
        'leverage': 5,
        'position_size': 0.06,  # 6% capital * 5x = 30% exposure
        'tp_percent': 0.008,  # 0.8%
        'sl_percent': 0.004,  # 0.4%
        'trailing_activation': 0.006,  # 0.6%
        'trailing_distance': 0.002,    # 0.2%
    },
    {
        'name': 'Very Aggressive 10x',
        'leverage': 10,
        'position_size': 0.04,  # 4% capital * 10x = 40% exposure
        'tp_percent': 0.006,  # 0.6%
        'sl_percent': 0.003,  # 0.3%
        'trailing_activation': 0.004,  # 0.4%
        'trailing_distance': 0.0015,   # 0.15%
    },
    {
        'name': 'Extreme 10x (Wider SL)',
        'leverage': 10,
        'position_size': 0.03,  # 3% capital * 10x = 30% exposure
        'tp_percent': 0.008,  # 0.8%
        'sl_percent': 0.004,  # 0.4% (biraz daha geniş)
        'trailing_activation': 0.005,  # 0.5%
        'trailing_distance': 0.002,    # 0.2%
    },
]

# Base strategy config (4h Trend + 50 Strength)
BASE_STRATEGY = {
    'min_fractal_strength': 50,
    'trend_timeframe': '4h',
    'trend_ema_period': 50,
    'fractal_patterns': ['Trending Up', 'Outside Bar'],
}


# ====================================================================================================
# VERİ YÜKLEME
# ====================================================================================================

class LeveragedDataLoader:
    """Multi-timeframe veri yükleyici"""

    def __init__(self):
        self.conn = psycopg2.connect(
            host='127.0.0.1',
            database='jesse_db',
            user='voidstring',
            password=''
        )

    def load_data(self, start_date: str, end_date: str, trend_tf: str = '4h') -> pd.DataFrame:
        """15m + trend timeframe verilerini yükle"""

        # Convert dates to Unix timestamps (milliseconds)
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

        # Trend timeframe EMA hesapla
        df_trend['ema_50'] = df_trend['close'].ewm(span=50, adjust=False).mean()

        # 15m'e merge et (forward-fill, no look-ahead)
        for col in ['close', 'ema_50']:
            df_15m[f'{trend_tf}_{col}'] = df_15m.index.map(
                lambda dt: df_trend[df_trend.index <= dt][col].iloc[-1]
                if len(df_trend[df_trend.index <= dt]) > 0 else np.nan
            )

        # Fraktal analiz ekle
        df_15m = self._add_fractal_analysis(df_15m)

        # NaN temizle
        df_15m.dropna(inplace=True)

        return df_15m

    def _add_fractal_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        """Basit fraktal pattern analizi"""

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

            # Outside Bar (Engulfing)
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

class LeveragedBacktester:
    """Kaldıraçlı backtest motoru"""

    def __init__(self, config: Dict):
        self.config = config
        self.capital = 10000
        self.commission_rate = 0.0004
        self.trades = []

    def check_entry_signal(self, row) -> bool:
        """Giriş sinyali kontrolü"""

        # Rule 1: Fraktal pattern
        if row['fractal_pattern'] not in BASE_STRATEGY['fractal_patterns']:
            return False

        # Rule 2: Fraktal strength
        if row['fractal_strength'] < BASE_STRATEGY['min_fractal_strength']:
            return False

        # Rule 3: Trend filter (4h)
        trend_tf = BASE_STRATEGY['trend_timeframe']
        if row[f'{trend_tf}_close'] <= row[f'{trend_tf}_ema_50']:
            return False

        return True

    def calculate_liquidation_price(self, entry_price: float, leverage: int) -> float:
        """Liquidation fiyatı hesapla (long pozisyon)"""
        # Binance Futures: Liquidation = Entry * (1 - 1/Leverage)
        # Ama biraz buffer ekleyelim
        liquidation = entry_price * (1 - 0.9 / leverage)
        return liquidation

    def run_backtest(self, df: pd.DataFrame) -> Dict:
        """Backtest çalıştır"""

        self.trades = []
        current_trade = None
        balance = self.capital
        leverage = self.config['leverage']

        for idx, row in df.iterrows():

            # Pozisyon yoksa, entry ara
            if current_trade is None:
                if self.check_entry_signal(row):
                    # Entry
                    position_value = balance * self.config['position_size'] * leverage
                    commission = position_value * self.commission_rate

                    # Liquidation price
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
                # Pozisyon varsa, exit kontrolü
                current_price = row['close']
                high_price = row['high']
                low_price = row['low']

                # Update highest price
                if high_price > current_trade['highest_price']:
                    current_trade['highest_price'] = high_price

                # Trailing stop aktivasyonu
                if not current_trade['trailing_active']:
                    activation_price = current_trade['entry_price'] * (1 + self.config['trailing_activation'])
                    if current_price >= activation_price:
                        current_trade['trailing_active'] = True
                        current_trade['trailing_stop'] = current_price * (1 - self.config['trailing_distance'])

                # Trailing stop güncelle
                if current_trade['trailing_active']:
                    new_trailing = current_trade['highest_price'] * (1 - self.config['trailing_distance'])
                    if new_trailing > current_trade['trailing_stop']:
                        current_trade['trailing_stop'] = new_trailing

                # Exit kontrolü
                exit_type = None
                exit_price = None

                # 1. Liquidation (En kötü durum)
                if low_price <= current_trade['liquidation_price']:
                    exit_type = 'Liquidation'
                    exit_price = current_trade['liquidation_price']

                # 2. Stop Loss
                elif low_price <= current_trade['sl_price']:
                    exit_type = 'SL'
                    exit_price = current_trade['sl_price']

                # 3. Take Profit
                elif high_price >= current_trade['tp_price']:
                    exit_type = 'TP'
                    exit_price = current_trade['tp_price']

                # 4. Trailing Stop
                elif current_trade['trailing_active'] and low_price <= current_trade['trailing_stop']:
                    exit_type = 'Trailing'
                    exit_price = current_trade['trailing_stop']

                # Exit varsa
                if exit_type:
                    exit_commission = current_trade['position_value'] * self.commission_rate

                    # Kaldıraçlı PnL hesapla
                    price_change_pct = (exit_price / current_trade['entry_price']) - 1
                    leveraged_pnl_pct = price_change_pct * leverage

                    # Net PnL (collateral üzerinden)
                    gross_pnl = current_trade['collateral'] * leveraged_pnl_pct
                    net_pnl = gross_pnl - current_trade['entry_commission'] - exit_commission

                    # Liquidation durumunda tüm collateral kaybedilir
                    if exit_type == 'Liquidation':
                        net_pnl = -current_trade['collateral']

                    balance += net_pnl

                    # Balance 0'ın altına düşerse bankrupt
                    if balance <= 0:
                        balance = 0

                    self.trades.append({
                        'entry_time': current_trade['entry_time'],
                        'exit_time': idx,
                        'entry_price': current_trade['entry_price'],
                        'exit_price': exit_price,
                        'exit_type': exit_type,
                        'pnl': net_pnl,
                        'pnl_pct': leveraged_pnl_pct,
                        'leverage': leverage,
                    })

                    current_trade = None

                    # Eğer balance 0 ise backtest bitsin
                    if balance <= 0:
                        print(f"  ⚠️  BANKRUPT! Balance: $0")
                        break

        # Final balance
        final_balance = balance
        roi = ((final_balance - self.capital) / self.capital) * 100

        # Metrics
        trades_df = pd.DataFrame(self.trades)

        if len(trades_df) > 0:
            wins = trades_df[trades_df['pnl'] > 0]
            losses = trades_df[trades_df['pnl'] <= 0]

            win_rate = len(wins) / len(trades_df) * 100 if len(trades_df) > 0 else 0

            total_profit = wins['pnl'].sum() if len(wins) > 0 else 0
            total_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 1
            profit_factor = total_profit / total_loss if total_loss > 0 else 0

            total_commission = (len(trades_df) * 2) * (self.capital * self.config['position_size'] * leverage * self.commission_rate)

            exit_counts = trades_df['exit_type'].value_counts().to_dict()

            # Max drawdown
            cumulative_pnl = trades_df['pnl'].cumsum()
            running_max = cumulative_pnl.expanding().max()
            drawdown = cumulative_pnl - running_max
            max_drawdown = (drawdown.min() / self.capital) * 100 if len(drawdown) > 0 else 0

            # Average trade metrics
            avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
            avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0

            # Liquidation count
            liquidations = len(trades_df[trades_df['exit_type'] == 'Liquidation'])
        else:
            win_rate = 0
            profit_factor = 0
            total_commission = 0
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
            'total_commission': total_commission,
            'exit_counts': exit_counts,
            'max_drawdown': max_drawdown,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'liquidations': liquidations,
        }


# ====================================================================================================
# MAIN
# ====================================================================================================

def main():
    print("=" * 100)
    print("KALDIRAÇLI FİLTRE OPTİMİZASYONU")
    print("=" * 100)
    print()
    print(f"Base Strateji: {BASE_STRATEGY['trend_timeframe']} Trend + {BASE_STRATEGY['min_fractal_strength']} Strength")
    print()

    # Data loader
    loader = LeveragedDataLoader()

    print("📊 Veri yükleniyor...")

    # Load data once
    df = loader.load_data(
        start_date='2024-01-01',
        end_date='2024-10-31',
        trend_tf=BASE_STRATEGY['trend_timeframe']
    )
    print(f"✅ Veri yüklendi: {len(df)} mum")
    print()

    results = []

    for i, config in enumerate(LEVERAGE_CONFIGS):
        print(f"{'='*100}")
        print(f"[{i+1}/{len(LEVERAGE_CONFIGS)}] Test: {config['name']}")
        print(f"{'='*100}")
        print(f"  Leverage: {config['leverage']}x")
        print(f"  Position Size: {config['position_size']*100:.0f}% (Exposure: {config['position_size']*config['leverage']*100:.0f}%)")
        print(f"  TP/SL: {config['tp_percent']*100:.2f}% / {config['sl_percent']*100:.2f}%")

        # Backtest
        backtester = LeveragedBacktester(config)
        result = backtester.run_backtest(df.copy())

        # Sonuçları sakla
        result['config_name'] = config['name']
        result['leverage'] = config['leverage']
        result['position_size'] = config['position_size']
        result['exposure'] = config['position_size'] * config['leverage']
        results.append(result)

        # Özet
        print(f"\n📈 SONUÇ:")
        print(f"  ROI: {result['roi']:.2f}%")
        print(f"  Final Balance: ${result['final_balance']:.2f}")
        print(f"  Trade Sayısı: {result['num_trades']}")
        print(f"  Win Rate: {result['win_rate']:.1f}%")
        print(f"  Profit Factor: {result['profit_factor']:.2f}")
        print(f"  Max Drawdown: {result['max_drawdown']:.2f}%")
        print(f"  Komisyon: ${result['total_commission']:.2f}")
        print(f"  Avg Win: ${result['avg_win']:.2f}")
        print(f"  Avg Loss: ${result['avg_loss']:.2f}")

        if result['liquidations'] > 0:
            print(f"  ⚠️  Liquidations: {result['liquidations']}")

        if result['exit_counts']:
            print(f"\n  Çıkış Dağılımı:")
            for exit_type, count in result['exit_counts'].items():
                pct = (count / result['num_trades']) * 100
                print(f"    {exit_type}: {count} ({pct:.1f}%)")

        print()

    # Karşılaştırma tablosu
    print("=" * 100)
    print("📊 GENEL KARŞILAŞTIRMA")
    print("=" * 100)

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('roi', ascending=False)

    print("\nSıralama (ROI'ye göre):\n")
    print(f"{'Rank':<5} {'Konfigürasyon':<30} {'Leverage':<10} {'ROI':<12} {'Trades':<10} {'Win%':<10} {'PF':<10} {'MaxDD':<10}")
    print("-" * 100)

    for idx, row in results_df.iterrows():
        rank = results_df.index.get_loc(idx) + 1
        liq_warning = " ⚠️" if row['liquidations'] > 0 else ""
        print(f"{rank:<5} {row['config_name']:<30} {row['leverage']:<10}x {row['roi']:>10.2f}% {row['num_trades']:>8} {row['win_rate']:>8.1f}% {row['profit_factor']:>8.2f} {row['max_drawdown']:>8.2f}%{liq_warning}")

    # En iyi
    best = results_df.iloc[0]
    print("\n" + "=" * 100)
    print("🏆 EN İYİ KONFİGÜRASYON")
    print("=" * 100)
    print(f"\nKonfigürasyon: {best['config_name']}")
    print(f"Leverage: {best['leverage']}x")
    print(f"ROI: {best['roi']:.2f}%")
    print(f"Final Balance: ${best['final_balance']:.2f}")
    print(f"Trade Sayısı: {best['num_trades']}")
    print(f"Win Rate: {best['win_rate']:.1f}%")
    print(f"Profit Factor: {best['profit_factor']:.2f}")
    print(f"Max Drawdown: {best['max_drawdown']:.2f}%")

    if best['liquidations'] > 0:
        print(f"⚠️  Liquidations: {best['liquidations']}")

    # Risk analizi
    print("\n" + "=" * 100)
    print("📊 RİSK ANALİZİ")
    print("=" * 100)

    # No leverage vs best leverage
    no_lev = results_df[results_df['leverage'] == 1].iloc[0]
    print(f"\nKarşılaştırma (No Leverage vs {best['config_name']}):")
    print(f"  ROI: {no_lev['roi']:.2f}% → {best['roi']:.2f}% ({best['roi']/no_lev['roi']:.2f}x)")
    print(f"  Max Drawdown: {no_lev['max_drawdown']:.2f}% → {best['max_drawdown']:.2f}%")
    print(f"  Risk/Reward: {abs(best['roi']/best['max_drawdown']):.2f}")

    print("\n" + "=" * 100)
    if best['roi'] > 0 and best['liquidations'] == 0:
        print("✅ BAŞARILI KALDIRAÇLI STRATEJİ BULUNDU!")
        print(f"\nÖnerilen Kaldıraç: {best['leverage']}x")
        print(f"Beklenen Yıllık ROI: ~{best['roi'] * 1.2:.1f}% (10 ay veriden extrapolate)")
    elif best['roi'] > 0 and best['liquidations'] > 0:
        print("⚠️  POZİTİF SONUÇ AMA LİKİDASYON RİSKİ VAR!")
        print(f"\nKaldıraç {best['leverage']}x çok agresif olabilir.")
        print("Daha düşük kaldıraç önerilir.")
    else:
        print("❌ TÜM KALDIRAÇ SEVİYELERİ NEGATİF")
        print("\nKaldıraç bu strateji için uygun değil.")
        print("Farklı TP/SL parametreleri denenebilir.")
    print("=" * 100)


if __name__ == '__main__':
    main()
