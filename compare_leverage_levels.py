"""
LEVERAGE LEVELS COMPARISON - Kaldıraç Seviyelerini Karşılaştır
═══════════════════════════════════════════════════════════
2x, 3x, 5x kaldıraçlı stratejileri backtest ile karşılaştır

TESTLER:
- 2023-2024 verileri (2 yıl)
- 1h timeframe (win rate %63.4)
- Komisyon dahil
- Time-based exit (gün sonunda kapat)
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from leveraged_intraday_config import (
    LEVERAGED_2X_CONFIG,
    LEVERAGED_3X_CONFIG,
    LEVERAGED_5X_CONFIG
)


class LeveragedBacktest:
    """Kaldıraçlı backtest engine"""

    def __init__(self, config, initial_capital=10000):
        self.config = config
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = None
        self.trades = []
        self.balance_history = [initial_capital]
        self.commission_paid = 0
        self.liquidations = 0

        # Günlük limitler
        self.daily_trades = {}
        self.daily_loss = {}

    def load_data(self, start_date, end_date):
        """1h verilerini yükle"""
        print(f"  ⏳ Veri yükleniyor ({start_date} - {end_date})...")

        conn = psycopg2.connect(
            host='127.0.0.1',
            database='jesse_db',
            user='voidstring',
            password=''
        )

        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)

        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candle
            WHERE exchange = 'Binance Futures'
            AND symbol = 'BTC-USDT'
            AND timeframe = '1h'
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp ASC
        """

        df = pd.read_sql_query(query, conn, params=(start_ts, end_ts))
        conn.close()

        print(f"  ✅ {len(df)} mum yüklendi")
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
        """Komisyon hesapla (kaldıraçlı pozisyon üzerinden)"""
        real_position = price * quantity * self.config['leverage']
        return real_position * self.config['commission']

    def check_daily_limits(self, current_date):
        """Günlük limitleri kontrol et"""
        date_key = current_date.strftime('%Y-%m-%d')

        # Trade limiti
        daily_trades = self.daily_trades.get(date_key, 0)
        if daily_trades >= self.config['max_daily_trades']:
            return False, 'max_daily_trades'

        # Kayıp limiti
        daily_loss_pct = self.daily_loss.get(date_key, 0)
        if daily_loss_pct <= -self.config['max_daily_loss_pct']:
            return False, 'max_daily_loss'

        return True, None

    def check_liquidation(self, current_price):
        """Liquidation kontrolü"""
        if self.position is None:
            return False

        entry_price = self.position['entry_price']
        leverage = self.config['leverage']

        # Liquidation seviyesi hesapla
        # Basitleştirilmiş: entry_price * (1 - 1/leverage * 0.9)
        # 0.9 faktörü: Maintenance margin için buffer
        liquidation_price = entry_price * (1 - (1 / leverage) * 0.9)

        if current_price <= liquidation_price:
            return True

        return False

    def open_position(self, row):
        """Pozisyon aç"""
        current_time = datetime.fromtimestamp(row['timestamp'] / 1000)

        # Günlük limitleri kontrol et
        can_trade, reason = self.check_daily_limits(current_time)
        if not can_trade:
            return

        entry_price = row['close']

        # Position size hesapla (gerçek sermaye üzerinden)
        position_value = self.capital * self.config['position_size']
        quantity = position_value / entry_price

        # Kaldıraçlı pozisyon değeri
        leveraged_value = position_value * self.config['leverage']

        # Giriş komisyonu
        commission = self.calculate_commission(entry_price, quantity)
        self.capital -= commission
        self.commission_paid += commission

        self.position = {
            'entry_price': entry_price,
            'entry_time': current_time,
            'quantity': quantity,
            'position_value': position_value,
            'leveraged_value': leveraged_value,
            'pattern': row.get('fractal_pattern', 'Unknown'),
            'strength': row.get('fractal_strength', 0),
            'tp': entry_price * (1 + self.config['tp_percent']),
            'sl': entry_price * (1 - self.config['sl_percent']),
            'highest_price': entry_price,
            'trailing_active': False,
            'trailing_stop_price': 0,
            'breakeven_active': False,
            'entry_commission': commission,
            'partial_done': False,
        }

        # Günlük trade sayısını artır
        date_key = current_time.strftime('%Y-%m-%d')
        self.daily_trades[date_key] = self.daily_trades.get(date_key, 0) + 1

    def update_position(self, row):
        """Pozisyon güncelle ve çıkış kontrol et"""
        if self.position is None:
            return None

        current_price = row['close']
        high = row['high']
        low = row['low']
        current_time = datetime.fromtimestamp(row['timestamp'] / 1000)

        # Liquidation kontrolü
        if self.check_liquidation(current_price):
            return {
                'exit_reason': 'Liquidation',
                'exit_price': current_price,
                'exit_time': current_time
            }

        # Time-based exit (gün sonunda kapat)
        if 'force_exit_time' in self.config['trade_management']:
            exit_hour = int(self.config['trade_management']['force_exit_time'].split(':')[0])
            if current_time.hour >= exit_hour:
                return {
                    'exit_reason': 'Time Exit (EOD)',
                    'exit_price': current_price,
                    'exit_time': current_time
                }

        # Max hold time
        if 'max_hold_hours' in self.config['trade_management']:
            hours_held = (current_time - self.position['entry_time']).total_seconds() / 3600
            if hours_held >= self.config['trade_management']['max_hold_hours']:
                return {
                    'exit_reason': 'Time Exit (Max Hold)',
                    'exit_price': current_price,
                    'exit_time': current_time
                }

        # Highest price güncelle
        if high > self.position['highest_price']:
            self.position['highest_price'] = high

        # Kar/zarar hesapla (kaldıraçlı)
        price_change_pct = ((current_price - self.position['entry_price']) /
                           self.position['entry_price']) * 100
        leveraged_pnl_pct = price_change_pct * self.config['leverage']

        # Partial exit
        if (self.config['trade_management']['use_partial_exit'] and
            not self.position['partial_done']):
            for level in self.config['trade_management']['partial_exit_levels']:
                if price_change_pct >= level['price_pct']:
                    # Partial exit işlemi (şimdilik skip, basitlik için)
                    self.position['partial_done'] = True
                    break

        # Breakeven
        if (not self.position['breakeven_active'] and
            price_change_pct >= self.config['trade_management']['breakeven_activation']):
            offset = self.config['trade_management']['breakeven_offset']
            self.position['sl'] = self.position['entry_price'] * (1 + offset / 100)
            self.position['breakeven_active'] = True

        # Trailing stop
        if (not self.position['trailing_active'] and
            price_change_pct >= self.config['trade_management']['trailing_stop_activation']):
            self.position['trailing_active'] = True
            distance = self.config['trade_management']['trailing_stop_distance']
            self.position['trailing_stop_price'] = (
                self.position['highest_price'] * (1 - distance / 100)
            )

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
                'exit_time': current_time
            }

        return None

    def close_position(self, exit_info):
        """Pozisyon kapat"""
        exit_price = exit_info['exit_price']
        exit_time = exit_info['exit_time']
        exit_reason = exit_info['exit_reason']

        # Çıkış komisyonu
        exit_commission = self.calculate_commission(exit_price, self.position['quantity'])

        # Kar/zarar hesapla (kaldıraçlı!)
        price_change = exit_price - self.position['entry_price']
        price_change_pct = (price_change / self.position['entry_price'])

        # Kaldıraçlı kar/zarar
        leveraged_pnl = price_change * self.position['quantity'] * self.config['leverage']

        # Liquidation ise tüm pozisyon kaybedilir
        if exit_reason == 'Liquidation':
            leveraged_pnl = -self.position['position_value']
            self.liquidations += 1

        # Komisyonları düş
        net_pnl = leveraged_pnl - self.position['entry_commission'] - exit_commission

        self.capital += net_pnl
        self.commission_paid += exit_commission

        # Günlük kayıp güncelle
        date_key = exit_time.strftime('%Y-%m-%d')
        if net_pnl < 0:
            loss_pct = (net_pnl / self.initial_capital) * 100
            self.daily_loss[date_key] = self.daily_loss.get(date_key, 0) + loss_pct

        # Trade kaydı
        duration = exit_time - self.position['entry_time']

        self.trades.append({
            'entry_time': self.position['entry_time'],
            'exit_time': exit_time,
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'price_change_pct': price_change_pct * 100,
            'leveraged_pnl': leveraged_pnl,
            'commission': self.position['entry_commission'] + exit_commission,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason,
            'pattern': self.position['pattern'],
            'strength': self.position['strength'],
            'duration': duration,
        })

        self.balance_history.append(self.capital)
        self.position = None

    def run(self, start_date='2023-01-01', end_date='2024-12-31'):
        """Backtest çalıştır"""
        df = self.load_data(start_date, end_date)

        if len(df) < 100:
            print("  ❌ Yetersiz veri!")
            return None

        df = self.analyze_data(df)

        print(f"  🚀 Backtest başlıyor ({len(df)} mum)...")

        for idx in range(len(df)):
            row = df.iloc[idx]

            if self.position:
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

        total_pnl = self.capital - self.initial_capital
        roi = (total_pnl / self.initial_capital) * 100

        winning = [t for t in self.trades if t['net_pnl'] > 0]
        losing = [t for t in self.trades if t['net_pnl'] <= 0]

        win_rate = len(winning) / len(self.trades) * 100 if self.trades else 0

        # Max drawdown
        balance_array = np.array(self.balance_history)
        peak = np.maximum.accumulate(balance_array)
        drawdown = ((balance_array - peak) / peak) * 100
        max_dd = drawdown.min()

        # Profit factor
        total_wins = sum([t['net_pnl'] for t in winning]) if winning else 0
        total_losses = abs(sum([t['net_pnl'] for t in losing])) if losing else 1
        pf = total_wins / total_losses if total_losses > 0 else float('inf')

        # Sharpe ratio (basitleştirilmiş)
        returns = [t['net_pnl'] / self.initial_capital for t in self.trades]
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if len(returns) > 1 else 0

        return {
            'config_name': self.config['name'],
            'leverage': self.config['leverage'],
            'roi': roi,
            'total_pnl': total_pnl,
            'num_trades': len(self.trades),
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'profit_factor': pf,
            'sharpe_ratio': sharpe,
            'commission_paid': self.commission_paid,
            'commission_pct': (self.commission_paid / self.initial_capital) * 100,
            'avg_pnl': total_pnl / len(self.trades) if self.trades else 0,
            'liquidations': self.liquidations,
            'trades': self.trades,
            'final_balance': self.capital,
        }


def main():
    """3 kaldıraç seviyesini karşılaştır"""
    print("\n" + "="*100)
    print("LEVERAGE LEVELS COMPARISON - Kaldıraçlı Backtest Karşılaştırması")
    print("="*100)
    print("""
Test Parametreleri:
  - Timeframe: 1h
  - Periyot: 2023-2024 (2 yıl)
  - Komisyon: %0.04 (Binance Futures)
  - Kaldıraç Seviyeleri: 2x, 3x, 5x
  - Sermaye: $10,000
  - Time Exit: Pozisyonlar gün sonunda kapanır
    """)

    configs = [
        LEVERAGED_2X_CONFIG,
        LEVERAGED_3X_CONFIG,
        LEVERAGED_5X_CONFIG,
    ]

    results = []

    for config in configs:
        print(f"\n{'='*100}")
        print(f"🧪 {config['name']} (Kaldıraç: {config['leverage']}x)")
        print(f"{'='*100}")

        bt = LeveragedBacktest(config)
        result = bt.run()

        if result:
            results.append(result)

    if not results:
        print("\n❌ Hiç sonuç üretilemedi!")
        return

    # Sonuçları yazdır
    print("\n" + "="*100)
    print("KARŞILAŞTIRMA TABLOSU")
    print("="*100)
    print(f"\n{'Kaldıraç':<12} {'ROI':<12} {'Trades':<10} {'Win%':<10} {'MaxDD':<12} "
          f"{'PF':<8} {'Sharpe':<10} {'Liq':<8} {'Komisyon':<12}")
    print("-" * 100)

    for r in results:
        print(f"{r['leverage']}x{'':<10} "
              f"{r['roi']:>+6.2f}%{'':<5} "
              f"{r['num_trades']:<10} "
              f"{r['win_rate']:>5.1f}%{'':<4} "
              f"{r['max_drawdown']:>6.2f}%{'':<5} "
              f"{r['profit_factor']:>5.2f}{'':<3} "
              f"{r['sharpe_ratio']:>6.2f}{'':<4} "
              f"{r['liquidations']:<8} "
              f"${r['commission_paid']:>7.2f}")

    # En iyi config
    best = max(results, key=lambda x: x['roi'])

    print("\n" + "="*100)
    print(f"🏆 EN İYİ: {best['config_name']} ({best['leverage']}x Kaldıraç)")
    print("="*100)
    print(f"""
   💰 Başlangıç Sermaye: $10,000.00
   💰 Final Sermaye: ${best['final_balance']:,.2f}
   📈 ROI: {best['roi']:+.2f}%
   💵 Net Kar: ${best['total_pnl']:+,.2f}

   📊 Trade Sayısı: {best['num_trades']}
   ✅ Win Rate: {best['win_rate']:.1f}%
   🛡️  Max Drawdown: {best['max_drawdown']:.2f}%
   ⚖️  Profit Factor: {best['profit_factor']:.2f}
   📉 Sharpe Ratio: {best['sharpe_ratio']:.2f}

   💸 Komisyon: ${best['commission_paid']:.2f} ({best['commission_pct']:.2f}%)
   📈 Ortalama Kar/Trade: ${best['avg_pnl']:.2f}
   ⚠️  Liquidation Sayısı: {best['liquidations']}
    """)

    # Çıkış sebepleri
    print("="*100)
    print(f"🎯 ÇIKIŞ SEBEPLERİ ({best['config_name']}):")
    print("="*100)

    exit_reasons = {}
    for t in best['trades']:
        reason = t['exit_reason']
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(best['trades'])) * 100
        print(f"   {reason:<30} {count:>3} trade ({pct:.1f}%)")

    # Aylık performans
    print("\n" + "="*100)
    print("📅 AYLIK PERFORMANS (En İyi Config):")
    print("="*100)

    monthly_pnl = {}
    for t in best['trades']:
        month_key = t['entry_time'].strftime('%Y-%m')
        monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + t['net_pnl']

    for month in sorted(monthly_pnl.keys()):
        pnl = monthly_pnl[month]
        pnl_pct = (pnl / 10000) * 100
        print(f"   {month}: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")

    # Karşılaştırmalı analiz
    print("\n" + "="*100)
    print("📊 KARŞILAŞTIRMALI ANALİZ")
    print("="*100)

    print(f"\n{'Metrik':<30} {'2x':<15} {'3x':<15} {'5x':<15}")
    print("-" * 100)

    metrics = [
        ('ROI', 'roi', '%'),
        ('Win Rate', 'win_rate', '%'),
        ('Profit Factor', 'profit_factor', ''),
        ('Max Drawdown', 'max_drawdown', '%'),
        ('Sharpe Ratio', 'sharpe_ratio', ''),
        ('Komisyon', 'commission_paid', '$'),
        ('Liquidation', 'liquidations', ''),
    ]

    for label, key, unit in metrics:
        values = []
        for r in results:
            val = r[key]
            if unit == '%':
                values.append(f"{val:+.2f}%")
            elif unit == '$':
                values.append(f"${val:.2f}")
            else:
                values.append(f"{val:.2f}")

        print(f"{label:<30} {values[0]:<15} {values[1]:<15} {values[2]:<15}")

    print("\n" + "="*100)
    print("✅ ÖNERİLER")
    print("="*100)

    # Best config belirle
    if best['leverage'] == 2:
        print("""
🎯 2x KALDIRAÇ KAZANDI!

Neden En İyi:
✅ En düşük risk
✅ Daha geniş stop loss (noise'dan etkilenmiyor)
✅ Liquidation riski minimal
✅ Daha iyi uyku (daha az stres)

Sonraki Adımlar:
1. Paper trading ile 1 ay test et
2. $500 ile gerçek başla
3. İlk 10 trade'den sonra değerlendir
4. Başarılıysa kademeli artır
        """)
    elif best['leverage'] == 3:
        print("""
🎯 3x KALDIRAÇ KAZANDI!

Neden En İyi:
✅ İyi risk/reward dengesi
✅ Kabul edilebilir drawdown
⚠️  Daha dikkatli takip gerekir
⚠️  Liquidation riski var ama düşük

Sonraki Adımlar:
1. Paper trading ile 1 ay test et
2. Günlük stop loss limiti koy (%3)
3. $300-500 ile gerçek başla
4. İlk 10 trade başarılıysa devam et
        """)
    else:
        print("""
⚠️  5x KALDIRAÇ KAZANDI AMA DİKKAT!

Neden Kazandı:
✅ En yüksek kazanç potansiyeli
❌ En yüksek risk!
❌ Liquidation riski ciddi
❌ Çok dar stop loss

Sonraki Adımlar:
1. Paper trading ile EN AZ 2 ay test et
2. %1 kural: Trade başına max %1 risk
3. Çok küçük başla: $100-200
4. Günlük limit: Sadece 1 trade!
5. 3 kayıp = 1 hafta ara
        """)

    print("="*100)


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')

    main()
