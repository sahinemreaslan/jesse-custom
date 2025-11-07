"""
INTRADAY BACKTEST - 15 Dakikalık Strateji Testi
═══════════════════════════════════════════════════════════
15 dakikalık mumlarla intraday strateji backtesti
30 günlük veri ile hızlı test
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from intraday_strategy_config import INTRADAY_CONFIG


class IntradayBacktest:
    """Intraday strategy backtest engine"""

    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = None
        self.trades = []
        self.config = INTRADAY_CONFIG

        print("="*80)
        print("INTRADAY BACKTEST - 15 DAKİKALIK STRATEJİ")
        print("="*80)
        print(f"\n💰 Başlangıç Sermayesi: ${initial_capital:,.2f}")
        print(f"📊 Timeframe: 15 dakika")
        print(f"📋 TP: {self.config['tp_percent']*100}%, SL: {self.config['sl_percent']*100}%")
        print("="*80 + "\n")

    def load_data(self):
        """15 dakikalık verileri yükle"""
        print("⏳ Veritabanından 15 dakikalık veriler yükleniyor...")

        conn = psycopg2.connect(
            host='127.0.0.1',
            database='jesse_db',
            user='voidstring',
            password=''
        )

        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candle
            WHERE exchange = 'Binance Futures'
            AND symbol = 'BTC-USDT'
            AND timeframe = '15m'
            ORDER BY timestamp ASC
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        print(f"✅ {len(df)} mum yüklendi")
        print(f"   Başlangıç: {datetime.fromtimestamp(df.iloc[0]['timestamp']/1000).strftime('%Y-%m-%d %H:%M')}")
        print(f"   Bitiş: {datetime.fromtimestamp(df.iloc[-1]['timestamp']/1000).strftime('%Y-%m-%d %H:%M')}\n")

        return df

    def analyze_data(self, df):
        """Fraktal analiz uygula"""
        print("⏳ Fraktal analiz yapılıyor...")

        # Fraktal analiz
        df = FractalAnalyzer.analyze_series(df)

        # Multi-timeframe scoring
        analyzer = MultiTimeframeFractalAnalyzer(weights=self.config['weights'])
        df = analyzer.calculate_fractal_score(df)

        print(f"✅ Analiz tamamlandı\n")

        return df

    def check_entry(self, row):
        """Giriş sinyali kontrolü"""
        pattern = row.get('fractal_pattern', 'Unknown')
        strength = row.get('fractal_strength', 0)

        if pattern in self.config['entry_patterns'] and strength >= self.config['min_strength']:
            return True, pattern, strength

        return False, None, None

    def open_position(self, row, pattern, strength):
        """Pozisyon aç"""
        if self.position is not None:
            return

        entry_price = row['close']
        timestamp = datetime.fromtimestamp(row['timestamp'] / 1000)
        qty = (self.capital * self.config['position_size']) / entry_price

        self.position = {
            'entry_time': timestamp,
            'entry_price': entry_price,
            'quantity': qty,
            'remaining_qty': qty,
            'pattern': pattern,
            'strength': strength,
            'tp': entry_price * (1 + self.config['tp_percent']),
            'sl': entry_price * (1 - self.config['sl_percent']),
            'stop_loss': entry_price * (1 - self.config['sl_percent']),
            'trailing_stop_price': 0,
            'breakeven_active': False,
            'trailing_active': False,
            'highest_price': entry_price,
            'partial_done': False,
        }

    def update_position(self, row):
        """Pozisyon yönetimi"""
        if self.position is None:
            return None

        current_price = row['close']
        high = row['high']
        low = row['low']
        timestamp = datetime.fromtimestamp(row['timestamp'] / 1000)

        # En yüksek fiyat güncelle
        if high > self.position['highest_price']:
            self.position['highest_price'] = high

        # Kar/zarar hesapla
        profit_pct = ((current_price - self.position['entry_price']) / self.position['entry_price']) * 100

        # Partial exit
        if (self.config['trade_management']['use_partial_exit'] and
            not self.position['partial_done']):
            for level in self.config['trade_management']['partial_exit_levels']:
                if profit_pct >= level['price_pct']:
                    exit_qty = self.position['quantity'] * level['qty_pct']
                    profit = (current_price - self.position['entry_price']) * exit_qty
                    self.capital += profit
                    self.position['remaining_qty'] -= exit_qty
                    self.position['partial_done'] = True
                    break

        # Breakeven
        if (not self.position['breakeven_active'] and
            profit_pct >= self.config['trade_management']['breakeven_activation']):
            self.position['sl'] = self.position['entry_price'] * (
                1 + self.config['trade_management']['breakeven_offset'] / 100
            )
            self.position['breakeven_active'] = True

        # Trailing stop aktivasyonu
        if (not self.position['trailing_active'] and
            profit_pct >= self.config['trade_management']['trailing_stop_activation']):
            self.position['trailing_active'] = True
            self.position['trailing_stop_price'] = self.position['highest_price'] * (
                1 - self.config['trade_management']['trailing_stop_distance'] / 100
            )

        # Trailing stop güncelle
        if self.position['trailing_active']:
            new_trailing = self.position['highest_price'] * (
                1 - self.config['trade_management']['trailing_stop_distance'] / 100
            )
            if new_trailing > self.position['trailing_stop_price']:
                self.position['trailing_stop_price'] = new_trailing

        # Çıkış kontrolü
        exit_reason = None
        exit_price = None

        # TP kontrolü (high ile)
        if high >= self.position['tp']:
            exit_reason = 'Take Profit'
            exit_price = self.position['tp']
        # SL kontrolü (low ile)
        elif low <= self.position['sl']:
            exit_reason = 'Stop Loss'
            exit_price = self.position['sl']
        # Trailing stop kontrolü (low ile)
        elif (self.position['trailing_active'] and
              low <= self.position['trailing_stop_price']):
            exit_reason = 'Trailing Stop'
            exit_price = self.position['trailing_stop_price']

        return exit_reason, exit_price if exit_price else current_price, timestamp

    def close_position(self, exit_price, exit_time, reason):
        """Pozisyon kapat"""
        if self.position is None:
            return

        profit = (exit_price - self.position['entry_price']) * self.position['remaining_qty']
        profit_pct = ((exit_price - self.position['entry_price']) / self.position['entry_price']) * 100

        self.capital += profit

        duration = exit_time - self.position['entry_time']

        trade = {
            'entry_time': self.position['entry_time'],
            'exit_time': exit_time,
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'profit': profit,
            'profit_pct': profit_pct,
            'exit_reason': reason,
            'pattern': self.position['pattern'],
            'strength': self.position['strength'],
            'duration': duration,
            'balance_after': self.capital,
        }

        self.trades.append(trade)
        self.position = None

    def run(self):
        """Backtest çalıştır"""
        # Veri yükle
        df = self.load_data()

        if len(df) == 0:
            print("❌ Veri bulunamadı!")
            return

        # Analiz yap
        df = self.analyze_data(df)

        print("🚀 Backtest başlıyor...\n")

        # Her mum için
        for idx in range(len(df)):
            row = df.iloc[idx]

            if self.position:
                # Pozisyon varsa güncelle
                result = self.update_position(row)

                if result:
                    exit_reason, exit_price, exit_time = result
                    if exit_reason:
                        self.close_position(exit_price, exit_time, exit_reason)
            else:
                # Pozisyon yoksa giriş kontrol et
                signal, pattern, strength = self.check_entry(row)

                if signal:
                    self.open_position(row, pattern, strength)

        # Açık pozisyon varsa kapat
        if self.position:
            last_row = df.iloc[-1]
            exit_time = datetime.fromtimestamp(last_row['timestamp'] / 1000)
            self.close_position(last_row['close'], exit_time, 'Backtest End')

        print("✅ Backtest tamamlandı!\n")
        self.print_results()

    def print_results(self):
        """Sonuçları yazdır"""
        print("="*80)
        print("INTRADAY BACKTEST SONUÇLARI")
        print("="*80)

        print(f"\n💰 SERMAYENİN DEĞİŞİMİ:")
        print(f"   Başlangıç: ${self.initial_capital:,.2f}")
        print(f"   Bitiş: ${self.capital:,.2f}")
        profit = self.capital - self.initial_capital
        roi = ((self.capital / self.initial_capital) - 1) * 100
        print(f"   Kar/Zarar: ${profit:+,.2f}")
        print(f"   ROI: {roi:+.2f}%")

        if len(self.trades) == 0:
            print("\n⚠️  Hiç trade yapılmadı!")
            print("="*80)
            return

        # Trade istatistikleri
        winning_trades = [t for t in self.trades if t['profit'] > 0]
        losing_trades = [t for t in self.trades if t['profit'] < 0]

        print(f"\n📊 TRADE İSTATİSTİKLERİ:")
        print(f"   Toplam Trade: {len(self.trades)}")
        print(f"   Kazanan: {len(winning_trades)} ({len(winning_trades)/len(self.trades)*100:.1f}%)")
        print(f"   Kaybeden: {len(losing_trades)} ({len(losing_trades)/len(self.trades)*100:.1f}%)")

        if winning_trades:
            avg_win = np.mean([t['profit'] for t in winning_trades])
            avg_win_pct = np.mean([t['profit_pct'] for t in winning_trades])
            print(f"   Ortalama Kazanç: ${avg_win:,.2f} ({avg_win_pct:.2f}%)")

        if losing_trades:
            avg_loss = np.mean([t['profit'] for t in losing_trades])
            avg_loss_pct = np.mean([t['profit_pct'] for t in losing_trades])
            print(f"   Ortalama Zarar: ${avg_loss:,.2f} ({avg_loss_pct:.2f}%)")

        # Süre istatistikleri
        durations = [t['duration'].total_seconds() / 3600 for t in self.trades]  # Saate çevir
        print(f"\n⏱️  SÜRE İSTATİSTİKLERİ:")
        print(f"   Ortalama Trade Süresi: {np.mean(durations):.1f} saat")
        print(f"   En Kısa Trade: {np.min(durations):.1f} saat")
        print(f"   En Uzun Trade: {np.max(durations):.1f} saat")

        # Çıkış sebepleri
        print(f"\n🚪 ÇIKIŞ SEBEPLERİ:")
        exit_reasons = {}
        for t in self.trades:
            reason = t['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

        for reason, count in exit_reasons.items():
            print(f"   {reason}: {count} ({count/len(self.trades)*100:.1f}%)")

        # Pattern başarı oranları
        print(f"\n📐 PATTERN BAŞARI ORANLARI:")
        pattern_stats = {}
        for t in self.trades:
            pattern = t['pattern']
            if pattern not in pattern_stats:
                pattern_stats[pattern] = {'total': 0, 'wins': 0}
            pattern_stats[pattern]['total'] += 1
            if t['profit'] > 0:
                pattern_stats[pattern]['wins'] += 1

        for pattern, stats in pattern_stats.items():
            win_rate = (stats['wins'] / stats['total']) * 100
            print(f"   {pattern}: {stats['wins']}/{stats['total']} ({win_rate:.1f}%)")

        print("\n" + "="*80 + "\n")

        # Son 5 trade
        print("📋 SON 5 TRADE:")
        print("-"*80)
        print(f"{'Giriş':<20} {'Çıkış':<20} {'Fiyat':<15} {'K/Z':<15} {'Sebep':<15}")
        print("-"*80)

        for t in self.trades[-5:]:
            entry_str = t['entry_time'].strftime('%Y-%m-%d %H:%M')
            exit_str = t['exit_time'].strftime('%Y-%m-%d %H:%M')
            price_str = f"${t['entry_price']:,.0f}"
            profit_str = f"${t['profit']:+,.2f}"
            reason_str = t['exit_reason'][:15]

            print(f"{entry_str:<20} {exit_str:<20} {price_str:<15} {profit_str:<15} {reason_str:<15}")

        print("="*80 + "\n")


def main():
    print("\n" + "="*80)
    print("INTRADAY BACKTEST - 15 DAKİKALIK STRATEJİ TESTİ")
    print("="*80)
    print("""
Bu backtest intraday stratejiyi 15 dakikalık mumlarla test eder.

Parametreler:
  - Timeframe: 15 dakika
  - TP: %2, SL: %1
  - Trailing: %1 / %0.5
  - Position Size: %15

Test verisi: Son 30 gün (2880 mum)
    """)

    capital = input("Başlangıç sermayesi (10000): ").strip() or "10000"
    capital = float(capital)

    print(f"\n✅ ${capital:,.2f} ile backtest başlatılıyor...\n")

    # Backtest
    bt = IntradayBacktest(initial_capital=capital)
    bt.run()


if __name__ == '__main__':
    main()
