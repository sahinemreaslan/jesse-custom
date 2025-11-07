"""
IMPROVED INTRADAY BACKTEST
═══════════════════════════════════════════════════════════
Düzeltmeler:
  ✅ Komisyon dahil
  ✅ Doğru ölçeklendirilmiş parametreler
  ✅ 3 farklı config karşılaştırması
  ✅ Detaylı performans analizi
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from intraday_optimized_config import (
    INTRADAY_OPTIMIZED_CONFIG,
    INTRADAY_AGGRESSIVE_CONFIG,
    INTRADAY_CONSERVATIVE_CONFIG
)


class ImprovedIntradayBacktest:
    """Geliştirilmiş Intraday Backtest"""

    def __init__(self, config, initial_capital=10000):
        self.config = config
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = None
        self.trades = []
        self.balance_history = [initial_capital]
        self.commission_paid = 0

    def load_data(self, days=30):
        """Son N günün 15 dakikalık verilerini yükle"""
        print(f"  ⏳ {days} günlük 15m veri yükleniyor...")

        conn = psycopg2.connect(
            host='127.0.0.1',
            database='jesse_db',
            user='voidstring',
            password=''
        )

        # Son N gün
        end_ts = int(datetime.now().timestamp() * 1000)
        start_ts = end_ts - (days * 24 * 60 * 60 * 1000)

        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candle
            WHERE exchange = 'Binance Futures'
            AND symbol = 'BTC-USDT'
            AND timeframe = '15m'
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp ASC
        """

        df = pd.read_sql_query(query, conn, params=(start_ts, end_ts))
        conn.close()

        if len(df) == 0:
            print("  ⚠️  Veri bulunamadı, tüm veriyi yüklüyorum...")
            conn = psycopg2.connect(
                host='127.0.0.1',
                database='jesse_db',
                user='voidstring',
                password=''
            )
            query_all = """
                SELECT timestamp, open, high, low, close, volume
                FROM candle
                WHERE exchange = 'Binance Futures'
                AND symbol = 'BTC-USDT'
                AND timeframe = '15m'
                ORDER BY timestamp DESC
                LIMIT %s
            """
            mum_sayisi = days * 24 * 4  # 4 mum/saat
            df = pd.read_sql_query(query_all, conn, params=(mum_sayisi,))
            df = df.sort_values('timestamp').reset_index(drop=True)
            conn.close()

        print(f"  ✅ {len(df)} mum yüklendi")
        if len(df) > 0:
            print(f"     {datetime.fromtimestamp(df.iloc[0]['timestamp']/1000).strftime('%Y-%m-%d %H:%M')}")
            print(f"     → {datetime.fromtimestamp(df.iloc[-1]['timestamp']/1000).strftime('%Y-%m-%d %H:%M')}")

        return df

    def analyze_data(self, df):
        """Fraktal analiz"""
        print("  ⏳ Fraktal analiz...")
        df = FractalAnalyzer.analyze_series(df)
        analyzer = MultiTimeframeFractalAnalyzer(weights=self.config['weights'])
        df = analyzer.calculate_fractal_score(df)
        print("  ✅ Analiz tamam")
        return df

    def calculate_commission(self, price, quantity):
        """Komisyon hesapla"""
        trade_value = price * quantity
        return trade_value * self.config['commission']

    def open_position(self, row):
        """Pozisyon aç"""
        entry_price = row['close']
        quantity = (self.capital * self.config['position_size']) / entry_price

        # Giriş komisyonu
        commission = self.calculate_commission(entry_price, quantity)
        self.commission_paid += commission

        self.position = {
            'entry_price': entry_price,
            'entry_time': datetime.fromtimestamp(row['timestamp'] / 1000),
            'quantity': quantity,
            'pattern': row.get('fractal_pattern', 'Unknown'),
            'strength': row.get('fractal_strength', 0),
            'tp': entry_price * (1 + self.config['tp_percent']),
            'sl': entry_price * (1 - self.config['sl_percent']),
            'highest_price': entry_price,
            'trailing_active': False,
            'trailing_stop_price': 0,
            'breakeven_active': False,
            'entry_commission': commission,
        }

    def update_position(self, row):
        """Pozisyon güncelle ve çıkış kontrol et"""
        if self.position is None:
            return None

        current_price = row['close']
        high = row['high']
        low = row['low']

        # Highest price
        if high > self.position['highest_price']:
            self.position['highest_price'] = high

        # Profit hesapla
        profit_pct = ((current_price - self.position['entry_price']) /
                     self.position['entry_price']) * 100

        # Breakeven
        if (not self.position['breakeven_active'] and
            profit_pct >= self.config['trade_management']['breakeven_activation']):
            offset = self.config['trade_management']['breakeven_offset']
            self.position['sl'] = self.position['entry_price'] * (1 + offset / 100)
            self.position['breakeven_active'] = True

        # Trailing stop aktivasyon
        if (not self.position['trailing_active'] and
            profit_pct >= self.config['trade_management']['trailing_stop_activation']):
            self.position['trailing_active'] = True
            distance = self.config['trade_management']['trailing_stop_distance']
            self.position['trailing_stop_price'] = (
                self.position['highest_price'] * (1 - distance / 100)
            )

        # Trailing stop güncelle
        if self.position['trailing_active']:
            distance = self.config['trade_management']['trailing_stop_distance']
            new_trailing = self.position['highest_price'] * (1 - distance / 100)
            if new_trailing > self.position['trailing_stop_price']:
                self.position['trailing_stop_price'] = new_trailing

        # Çıkış kontrolü
        exit_reason = None
        exit_price = None

        # TP
        if high >= self.position['tp']:
            exit_reason = 'Take Profit'
            exit_price = self.position['tp']
        # SL
        elif low <= self.position['sl']:
            exit_reason = 'Stop Loss'
            exit_price = self.position['sl']
        # Trailing
        elif (self.position['trailing_active'] and
              low <= self.position['trailing_stop_price']):
            exit_reason = 'Trailing Stop'
            exit_price = self.position['trailing_stop_price']

        if exit_reason:
            return {
                'exit_reason': exit_reason,
                'exit_price': exit_price,
                'exit_time': datetime.fromtimestamp(row['timestamp'] / 1000)
            }

        return None

    def close_position(self, exit_info):
        """Pozisyon kapat"""
        exit_price = exit_info['exit_price']
        exit_time = exit_info['exit_time']
        exit_reason = exit_info['exit_reason']

        # Çıkış komisyonu
        exit_commission = self.calculate_commission(exit_price, self.position['quantity'])
        self.commission_paid += exit_commission

        # Kar/zarar
        gross_profit = (exit_price - self.position['entry_price']) * self.position['quantity']
        total_commission = self.position['entry_commission'] + exit_commission
        net_profit = gross_profit - total_commission

        self.capital += net_profit

        # Trade kaydı
        duration = exit_time - self.position['entry_time']
        profit_pct = ((exit_price - self.position['entry_price']) /
                     self.position['entry_price']) * 100

        self.trades.append({
            'entry_time': self.position['entry_time'],
            'exit_time': exit_time,
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'gross_profit': gross_profit,
            'commission': total_commission,
            'net_profit': net_profit,
            'profit_pct': profit_pct,
            'exit_reason': exit_reason,
            'pattern': self.position['pattern'],
            'strength': self.position['strength'],
            'duration': duration,
        })

        self.balance_history.append(self.capital)
        self.position = None

    def run(self, days=30):
        """Backtest çalıştır"""
        df = self.load_data(days)

        if len(df) < 100:
            print("  ❌ Yetersiz veri!")
            return None

        df = self.analyze_data(df)

        print(f"  🚀 Backtest başlıyor ({len(df)} mum)...")

        for idx in range(len(df)):
            row = df.iloc[idx]

            if self.position:
                # Pozisyon varsa güncelle
                exit_info = self.update_position(row)
                if exit_info:
                    self.close_position(exit_info)
            else:
                # Giriş kontrol
                pattern = row.get('fractal_pattern', 'Unknown')
                strength = row.get('fractal_strength', 0)

                if (pattern in self.config['entry_patterns'] and
                    strength >= self.config['min_strength']):
                    self.open_position(row)

        # Açık pozisyon varsa kapat
        if self.position:
            last_row = df.iloc[-1]
            exit_info = {
                'exit_price': last_row['close'],
                'exit_time': datetime.fromtimestamp(last_row['timestamp'] / 1000),
                'exit_reason': 'Backtest End'
            }
            self.close_position(exit_info)

        print(f"  ✅ Backtest tamamlandı: {len(self.trades)} trade")

        return self.get_results()

    def get_results(self):
        """Sonuçları hesapla"""
        if len(self.trades) == 0:
            return None

        total_profit = self.capital - self.initial_capital
        roi = (total_profit / self.initial_capital) * 100

        winning = [t for t in self.trades if t['net_profit'] > 0]
        losing = [t for t in self.trades if t['net_profit'] <= 0]

        win_rate = len(winning) / len(self.trades) * 100 if self.trades else 0

        # Max drawdown
        balance_array = np.array(self.balance_history)
        peak = np.maximum.accumulate(balance_array)
        drawdown = ((balance_array - peak) / peak) * 100
        max_dd = drawdown.min()

        # Profit factor
        total_wins = sum([t['net_profit'] for t in winning]) if winning else 0
        total_losses = abs(sum([t['net_profit'] for t in losing])) if losing else 1
        pf = total_wins / total_losses if total_losses > 0 else float('inf')

        return {
            'config_name': self.config['name'],
            'roi': roi,
            'total_profit': total_profit,
            'num_trades': len(self.trades),
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'profit_factor': pf,
            'commission_paid': self.commission_paid,
            'commission_pct': (self.commission_paid / self.initial_capital) * 100,
            'avg_profit': total_profit / len(self.trades) if self.trades else 0,
            'trades': self.trades,
        }


def compare_configs(days=30):
    """3 farklı config'i karşılaştır"""
    print("\n" + "="*100)
    print("IMPROVED INTRADAY BACKTEST - 3 KONFİGÜRASYON KARŞILAŞTIRMASI")
    print("="*100)

    configs = [
        INTRADAY_OPTIMIZED_CONFIG,
        INTRADAY_AGGRESSIVE_CONFIG,
        INTRADAY_CONSERVATIVE_CONFIG,
    ]

    results = []

    for config in configs:
        print(f"\n🧪 {config['name']}")
        print("-" * 100)

        bt = ImprovedIntradayBacktest(config)
        result = bt.run(days=days)

        if result:
            results.append(result)

    if not results:
        print("\n❌ Hiç sonuç üretilemedi!")
        return

    # Sonuçları yazdır
    print("\n" + "="*100)
    print("KARŞILAŞTIRMA TABLOSU")
    print("="*100)
    print(f"\n{'Config':<35} {'ROI':<12} {'Trades':<10} {'Win%':<10} {'MaxDD':<12} {'PF':<8} {'Komisyon':<12}")
    print("-" * 100)

    for r in results:
        print(f"{r['config_name']:<35} "
              f"{r['roi']:>+6.2f}%{'':<5} "
              f"{r['num_trades']:<10} "
              f"{r['win_rate']:>5.1f}%{'':<4} "
              f"{r['max_drawdown']:>6.2f}%{'':<5} "
              f"{r['profit_factor']:>5.2f}{'':<3} "
              f"${r['commission_paid']:>7.2f}")

    # En iyi config
    best = max(results, key=lambda x: x['roi'])

    print("\n" + "="*100)
    print(f"🏆 EN İYİ: {best['config_name']}")
    print("="*100)
    print(f"\n   💰 ROI: {best['roi']:+.2f}%")
    print(f"   📊 Trade Sayısı: {best['num_trades']}")
    print(f"   ✅ Win Rate: {best['win_rate']:.1f}%")
    print(f"   🛡️  Max Drawdown: {best['max_drawdown']:.2f}%")
    print(f"   ⚖️  Profit Factor: {best['profit_factor']:.2f}")
    print(f"   💸 Komisyon: ${best['commission_paid']:.2f} ({best['commission_pct']:.2f}%)")
    print(f"   📈 Ortalama Kar/Trade: ${best['avg_profit']:.2f}")

    # Son 5 trade
    if best['trades']:
        print(f"\n   📋 SON 5 TRADE:")
        print("   " + "-"*90)
        print(f"   {'Zaman':<20} {'Pattern':<15} {'Fiyat':<12} {'Net K/Z':<12} {'%':<10} {'Sebep':<15}")
        print("   " + "-"*90)

        for t in best['trades'][-5:]:
            time_str = t['entry_time'].strftime('%m-%d %H:%M')
            pattern = t['pattern'][:12]
            price = f"${t['entry_price']:,.0f}"
            profit = f"${t['net_profit']:+.2f}"
            pct = f"{t['profit_pct']:+.2f}%"
            reason = t['exit_reason'][:12]

            print(f"   {time_str:<20} {pattern:<15} {price:<12} {profit:<12} {pct:<10} {reason:<15}")

    print("\n" + "="*100)

    # Çıkış sebepleri (en iyi config için)
    print(f"\n🎯 ÇIKIŞ SEBEPLERİ ({best['config_name']}):")
    print("-" * 100)

    exit_reasons = {}
    for t in best['trades']:
        reason = t['exit_reason']
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(best['trades'])) * 100
        print(f"   {reason:<30} {count:>3} trade ({pct:.1f}%)")

    print("\n" + "="*100)


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')

    print("\n" + "="*100)
    print("IMPROVED INTRADAY BACKTEST")
    print("="*100)
    print("""
Bu backtest 3 farklı intraday konfigürasyonunu test eder:
  1. OPTIMIZED (Önerilen)
  2. AGGRESSIVE (Daha fazla trade)
  3. CONSERVATIVE (Daha az trade, yüksek kalite)

Düzeltmeler:
  ✅ Komisyon dahil edildi
  ✅ Parametreler volatilite bazlı ölçeklendirildi
  ✅ Partial exit kaldırıldı (komisyon maliyeti)
  ✅ Trailing stop optimize edildi
    """)

    days = input("Kaç günlük veri test edilsin? (30): ").strip() or "30"
    days = int(days)

    compare_configs(days=days)
