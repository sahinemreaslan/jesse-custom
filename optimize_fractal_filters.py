#!/usr/bin/env python3
"""
Fraktal Strateji Optimizasyonu - Daha Az Ama Daha Kaliteli Trade
================================================================

Farklı filtre kombinasyonlarını test edip en iyi performansı bulur.

Amaç: Trade sayısını azalt, kaliteyi artır
"""

import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


# ====================================================================================================
# KONFİGÜRASYONLAR - Test Edilecek Varyasyonlar
# ====================================================================================================

CONFIGURATIONS = [
    {
        'name': 'Baseline (Orijinal)',
        'min_fractal_strength': 30,
        'use_adx_filter': False,
        'use_volume_filter': False,
        'trend_timeframe': '1h',
        'trend_ema_period': 50,
        'tp_percent': 0.015,
        'sl_percent': 0.008,
    },
    {
        'name': 'Güçlü Fraktal (50+)',
        'min_fractal_strength': 50,
        'use_adx_filter': False,
        'use_volume_filter': False,
        'trend_timeframe': '1h',
        'trend_ema_period': 50,
        'tp_percent': 0.015,
        'sl_percent': 0.008,
    },
    {
        'name': 'Çok Güçlü Fraktal (60+)',
        'min_fractal_strength': 60,
        'use_adx_filter': False,
        'use_volume_filter': False,
        'trend_timeframe': '1h',
        'trend_ema_period': 50,
        'tp_percent': 0.015,
        'sl_percent': 0.008,
    },
    {
        'name': 'ADX Filtreli (Trending)',
        'min_fractal_strength': 40,
        'use_adx_filter': True,
        'adx_threshold': 25,
        'use_volume_filter': False,
        'trend_timeframe': '1h',
        'trend_ema_period': 50,
        'tp_percent': 0.015,
        'sl_percent': 0.008,
    },
    {
        'name': 'Volume Filtreli',
        'min_fractal_strength': 40,
        'use_adx_filter': False,
        'use_volume_filter': True,
        'volume_multiplier': 1.5,
        'trend_timeframe': '1h',
        'trend_ema_period': 50,
        'tp_percent': 0.015,
        'sl_percent': 0.008,
    },
    {
        'name': 'Hepsi Birlikte (Çok Sıkı)',
        'min_fractal_strength': 50,
        'use_adx_filter': True,
        'adx_threshold': 25,
        'use_volume_filter': True,
        'volume_multiplier': 1.5,
        'trend_timeframe': '1h',
        'trend_ema_period': 50,
        'tp_percent': 0.015,
        'sl_percent': 0.008,
    },
    {
        'name': '4h Büyük Trend + Güçlü Fraktal',
        'min_fractal_strength': 50,
        'use_adx_filter': False,
        'use_volume_filter': False,
        'trend_timeframe': '4h',
        'trend_ema_period': 50,
        'tp_percent': 0.015,
        'sl_percent': 0.008,
    },
]


# ====================================================================================================
# VERİ YÜKLEME
# ====================================================================================================

class OptimizedDataLoader:
    """Multi-timeframe veri yükleyici"""

    def __init__(self):
        self.conn = psycopg2.connect(
            host='127.0.0.1',
            database='jesse_db',
            user='voidstring',
            password=''
        )

    def load_data(self, start_date: str, end_date: str, trend_tf: str = '1h') -> pd.DataFrame:
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

        # 15m için ADX ve Volume Average hesapla
        df_15m = self._calculate_adx(df_15m)
        df_15m['volume_avg_20'] = df_15m['volume'].rolling(20).mean()

        # Fraktal analiz ekle
        df_15m = self._add_fractal_analysis(df_15m)

        # NaN temizle
        df_15m.dropna(inplace=True)

        return df_15m

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """ADX hesapla"""

        # True Range
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        # Directional Movement
        df['plus_dm'] = np.where(
            (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
            np.maximum(df['high'] - df['high'].shift(1), 0),
            0
        )
        df['minus_dm'] = np.where(
            (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
            np.maximum(df['low'].shift(1) - df['low'], 0),
            0
        )

        # Smoothed values
        df['atr'] = df['tr'].ewm(span=period, adjust=False).mean()
        df['plus_di'] = 100 * (df['plus_dm'].ewm(span=period, adjust=False).mean() / df['atr'])
        df['minus_di'] = 100 * (df['minus_dm'].ewm(span=period, adjust=False).mean() / df['atr'])

        # ADX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].ewm(span=period, adjust=False).mean()

        # Cleanup
        df.drop(['tr1', 'tr2', 'tr3', 'tr', 'plus_dm', 'minus_dm', 'plus_di', 'minus_di', 'dx'], axis=1, inplace=True)

        return df

    def _add_fractal_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        """Basit fraktal pattern analizi"""

        df['fractal_pattern'] = None
        df['fractal_strength'] = 0

        for i in range(2, len(df) - 2):
            current = df.iloc[i]
            prev2 = df.iloc[i-2]
            prev1 = df.iloc[i-1]
            next1 = df.iloc[i+1]
            next2 = df.iloc[i+2]

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

class OptimizedBacktester:
    """Backtest motoru"""

    def __init__(self, config: Dict):
        self.config = config
        self.capital = 10000
        self.commission_rate = 0.0004
        self.trades = []

    def check_entry_signal(self, row) -> bool:
        """Giriş sinyali kontrolü"""

        # Rule 1: Fraktal pattern
        if row['fractal_pattern'] not in ['Trending Up', 'Outside Bar']:
            return False

        # Rule 2: Fraktal strength
        if row['fractal_strength'] < self.config['min_fractal_strength']:
            return False

        # Rule 3: Trend filter
        trend_tf = self.config['trend_timeframe']
        if row[f'{trend_tf}_close'] <= row[f'{trend_tf}_ema_50']:
            return False

        # Rule 4 (Optional): ADX filter
        if self.config.get('use_adx_filter', False):
            if row['adx'] < self.config.get('adx_threshold', 25):
                return False

        # Rule 5 (Optional): Volume filter
        if self.config.get('use_volume_filter', False):
            vol_mult = self.config.get('volume_multiplier', 1.5)
            if row['volume'] < row['volume_avg_20'] * vol_mult:
                return False

        return True

    def run_backtest(self, df: pd.DataFrame) -> Dict:
        """Backtest çalıştır"""

        self.trades = []
        current_trade = None
        balance = self.capital

        for idx, row in df.iterrows():

            # Pozisyon yoksa, entry ara
            if current_trade is None:
                if self.check_entry_signal(row):
                    # Entry
                    position_size = balance * 0.10  # 10% of capital
                    commission = position_size * self.commission_rate

                    current_trade = {
                        'entry_time': idx,
                        'entry_price': row['close'],
                        'position_size': position_size,
                        'tp_price': row['close'] * (1 + self.config['tp_percent']),
                        'sl_price': row['close'] * (1 - self.config['sl_percent']),
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

                # Trailing stop aktivasyonu (1% kârda)
                if not current_trade['trailing_active']:
                    if current_price >= current_trade['entry_price'] * 1.01:
                        current_trade['trailing_active'] = True
                        current_trade['trailing_stop'] = current_price * 0.996  # 0.4% trail

                # Trailing stop güncelle
                if current_trade['trailing_active']:
                    new_trailing = current_trade['highest_price'] * 0.996
                    if new_trailing > current_trade['trailing_stop']:
                        current_trade['trailing_stop'] = new_trailing

                # Exit kontrolü
                exit_type = None
                exit_price = None

                # 1. Stop Loss
                if low_price <= current_trade['sl_price']:
                    exit_type = 'SL'
                    exit_price = current_trade['sl_price']

                # 2. Take Profit
                elif high_price >= current_trade['tp_price']:
                    exit_type = 'TP'
                    exit_price = current_trade['tp_price']

                # 3. Trailing Stop
                elif current_trade['trailing_active'] and low_price <= current_trade['trailing_stop']:
                    exit_type = 'Trailing'
                    exit_price = current_trade['trailing_stop']

                # Exit varsa
                if exit_type:
                    exit_commission = current_trade['position_size'] * self.commission_rate
                    pnl_pct = (exit_price / current_trade['entry_price']) - 1
                    pnl = current_trade['position_size'] * pnl_pct
                    net_pnl = pnl - current_trade['entry_commission'] - exit_commission

                    balance += net_pnl

                    self.trades.append({
                        'entry_time': current_trade['entry_time'],
                        'exit_time': idx,
                        'entry_price': current_trade['entry_price'],
                        'exit_price': exit_price,
                        'exit_type': exit_type,
                        'pnl': net_pnl,
                        'pnl_pct': pnl_pct,
                    })

                    current_trade = None

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

            total_commission = (len(trades_df) * 2) * (self.capital * 0.10 * self.commission_rate)

            exit_counts = trades_df['exit_type'].value_counts().to_dict()
        else:
            win_rate = 0
            profit_factor = 0
            total_commission = 0
            exit_counts = {}

        return {
            'roi': roi,
            'num_trades': len(trades_df),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_commission': total_commission,
            'exit_counts': exit_counts,
        }


# ====================================================================================================
# MAIN
# ====================================================================================================

def main():
    print("=" * 100)
    print("FİLTRE OPTİMİZASYONU - Daha Az Ama Daha Kaliteli Trade")
    print("=" * 100)
    print()

    # Data loader
    loader = OptimizedDataLoader()

    print("📊 Veri yükleniyor...")
    results = []

    for i, config in enumerate(CONFIGURATIONS):
        print(f"\n{'='*100}")
        print(f"[{i+1}/{len(CONFIGURATIONS)}] Test: {config['name']}")
        print(f"{'='*100}")

        # Veri yükle
        df = loader.load_data(
            start_date='2024-01-01',
            end_date='2024-10-31',
            trend_tf=config['trend_timeframe']
        )

        print(f"✅ Veri yüklendi: {len(df)} mum")

        # Backtest
        backtester = OptimizedBacktester(config)
        result = backtester.run_backtest(df)

        # Sonuçları sakla
        result['config_name'] = config['name']
        result['min_strength'] = config['min_fractal_strength']
        result['use_adx'] = config.get('use_adx_filter', False)
        result['use_volume'] = config.get('use_volume_filter', False)
        results.append(result)

        # Özet
        print(f"\n📈 SONUÇ:")
        print(f"  ROI: {result['roi']:.2f}%")
        print(f"  Trade Sayısı: {result['num_trades']}")
        print(f"  Win Rate: {result['win_rate']:.1f}%")
        print(f"  Profit Factor: {result['profit_factor']:.2f}")
        print(f"  Komisyon: ${result['total_commission']:.2f}")

        if result['exit_counts']:
            print(f"\n  Çıkış Dağılımı:")
            for exit_type, count in result['exit_counts'].items():
                pct = (count / result['num_trades']) * 100
                print(f"    {exit_type}: {count} ({pct:.1f}%)")

    # Karşılaştırma tablosu
    print("\n" + "=" * 100)
    print("📊 GENEL KARŞILAŞTIRMA")
    print("=" * 100)

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('roi', ascending=False)

    print("\nSıralama (ROI'ye göre):\n")
    print(f"{'Rank':<5} {'Konfigürasyon':<35} {'ROI':<10} {'Trades':<10} {'Win%':<10} {'PF':<10}")
    print("-" * 100)

    for idx, row in results_df.iterrows():
        rank = results_df.index.get_loc(idx) + 1
        print(f"{rank:<5} {row['config_name']:<35} {row['roi']:>8.2f}% {row['num_trades']:>8} {row['win_rate']:>8.1f}% {row['profit_factor']:>8.2f}")

    # En iyi
    best = results_df.iloc[0]
    print("\n" + "=" * 100)
    print("🏆 EN İYİ KONFİGÜRASYON")
    print("=" * 100)
    print(f"\nKonfigürasyon: {best['config_name']}")
    print(f"ROI: {best['roi']:.2f}%")
    print(f"Trade Sayısı: {best['num_trades']}")
    print(f"Win Rate: {best['win_rate']:.1f}%")
    print(f"Profit Factor: {best['profit_factor']:.2f}")

    # Öneri
    print("\n" + "=" * 100)
    if best['roi'] > 0:
        print("✅ POZİTİF SONUÇ BULUNDU!")
        print("\nBu konfigürasyonla devam et:")
        best_config = [c for c in CONFIGURATIONS if c['name'] == best['config_name']][0]
        print(f"  - Min Fractal Strength: {best_config['min_fractal_strength']}")
        print(f"  - ADX Filter: {best_config.get('use_adx_filter', False)}")
        print(f"  - Volume Filter: {best_config.get('use_volume_filter', False)}")
        print(f"  - Trend Timeframe: {best_config['trend_timeframe']}")
    else:
        print("❌ TÜM KONFİGÜRASYONLAR NEGATİF")
        print("\nDaha fazla optimizasyon gerekli. Öneriler:")
        print("  1. TP/SL oranını değiştir")
        print("  2. 30m base timeframe dene")
        print("  3. Tamamen farklı strateji dene (EMA cross, etc.)")

    print("=" * 100)


if __name__ == '__main__':
    main()
