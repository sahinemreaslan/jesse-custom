"""
INTRADAY PAPER TRADING - Gün İçi Trading
═══════════════════════════════════════════════════════════
15 dakikalık timeframe ile hızlı giriş/çıkış

Özellikler:
  - Her 1 DAKİKADA bir kontrol (demo için)
  - TP: %2, SL: %1
  - Trailing: %1 aktivasyon, %0.5 mesafe
  - Hızlı kar alma, sıkı risk kontrolü

Kullanım:
  python intraday_paper_trading.py

⚠️  PARA RİSKİ YOK - SADECE TEST!
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import ccxt
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from intraday_strategy_config import INTRADAY_CONFIG


class IntradayPaperTrading:
    """Intraday paper trading engine"""

    def __init__(self, symbol='BTC/USDT', initial_capital=10000):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.capital = initial_capital

        # Exchange
        self.exchange = ccxt.binance({'enableRateLimit': True})

        # Pozisyon
        self.position = None

        # Trades
        self.trades = []

        # Config
        self.config = INTRADAY_CONFIG

        print("="*80)
        print("INTRADAY PAPER TRADING - 15M TIMEFRAME")
        print("="*80)
        print(f"\n💰 Sermaye: ${initial_capital:,.2f}")
        print(f"📊 Symbol: {symbol}")
        print(f"⏰ Timeframe: 15 dakika")
        print(f"\n📋 PARAMETRELER:")
        print(f"   TP: {self.config['tp_percent']*100}%")
        print(f"   SL: {self.config['sl_percent']*100}%")
        print(f"   Trailing: {self.config['trade_management']['trailing_stop_activation']}% aktiv, {self.config['trade_management']['trailing_stop_distance']}% mesafe")
        print("\n⚠️  PAPER TRADING - GERÇEK PARA RİSKİ YOK!")
        print("="*80)

    def fetch_candles(self, limit=200):
        """15 dakikalık mumları çek"""
        try:
            candles = self.exchange.fetch_ohlcv(
                self.symbol,
                timeframe='15m',
                limit=limit
            )

            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df

        except Exception as e:
            print(f"⚠️  Veri hatası: {e}")
            return None

    def analyze(self, df):
        """Fraktal analiz"""
        if len(df) < 50:
            return None

        df = FractalAnalyzer.analyze_series(df)
        analyzer = MultiTimeframeFractalAnalyzer(weights=self.config['weights'])
        df = analyzer.calculate_fractal_score(df)

        return df

    def check_entry(self, df):
        """Giriş sinyali"""
        latest = df.iloc[-1]

        pattern = latest.get('fractal_pattern', 'Unknown')
        strength = latest.get('fractal_strength', 0)
        price = latest['close']

        if pattern in self.config['entry_patterns'] and strength >= self.config['min_strength']:
            return {
                'signal': True,
                'pattern': pattern,
                'strength': strength,
                'price': price,
                'timestamp': datetime.fromtimestamp(latest['timestamp'] / 1000)
            }

        return {'signal': False}

    def open_position(self, signal):
        """Pozisyon aç"""
        if self.position is not None:
            return

        entry_price = signal['price']
        qty = (self.capital * self.config['position_size']) / entry_price

        self.position = {
            'entry_time': signal['timestamp'],
            'entry_price': entry_price,
            'quantity': qty,
            'remaining_qty': qty,
            'pattern': signal['pattern'],
            'tp': entry_price * (1 + self.config['tp_percent']),
            'sl': entry_price * (1 - self.config['sl_percent']),
            'stop_loss': entry_price * (1 - self.config['sl_percent']),
            'trailing_stop_price': 0,
            'breakeven_active': False,
            'trailing_active': False,
            'highest_price': entry_price,
        }

        print(f"\n{'='*80}")
        print(f"🚀 POZİSYON AÇILDI (INTRADAY)")
        print(f"{'='*80}")
        print(f"   Zaman: {signal['timestamp'].strftime('%H:%M:%S')}")
        print(f"   Fiyat: ${entry_price:,.2f}")
        print(f"   Miktar: {qty:.6f} BTC")
        print(f"   Pattern: {signal['pattern']} ({signal['strength']:.1f})")
        print(f"\n   SEVİYELER:")
        print(f"      TP: ${self.position['tp']:,.2f} (+{self.config['tp_percent']*100}%)")
        print(f"      SL: ${self.position['sl']:,.2f} (-{self.config['sl_percent']*100}%)")
        print(f"{'='*80}\n")

    def update_position(self, current_price):
        """Pozisyon yönetimi"""
        if self.position is None:
            return

        # Highest price
        if current_price > self.position['highest_price']:
            self.position['highest_price'] = current_price

        # Kar/zarar
        profit_pct = ((current_price - self.position['entry_price']) / self.position['entry_price']) * 100

        # Partial exit
        if self.config['trade_management']['use_partial_exit'] and not hasattr(self.position, 'partial_done'):
            for level in self.config['trade_management']['partial_exit_levels']:
                if profit_pct >= level['price_pct']:
                    # Yarısını sat
                    exit_qty = self.position['quantity'] * level['qty_pct']
                    profit = (current_price - self.position['entry_price']) * exit_qty
                    self.capital += profit
                    self.position['remaining_qty'] -= exit_qty
                    self.position['partial_done'] = True
                    print(f"   💰 PARTIAL EXIT: %{level['qty_pct']*100} sat → ${profit:+,.2f}")
                    break

        # Breakeven
        if not self.position['breakeven_active'] and profit_pct >= self.config['trade_management']['breakeven_activation']:
            self.position['sl'] = self.position['entry_price'] * (1 + self.config['trade_management']['breakeven_offset'] / 100)
            self.position['breakeven_active'] = True
            print(f"   🛡️  BREAKEVEN: SL → ${self.position['sl']:,.2f}")

        # Trailing stop
        if not self.position['trailing_active'] and profit_pct >= self.config['trade_management']['trailing_stop_activation']:
            self.position['trailing_active'] = True
            self.position['trailing_stop_price'] = self.position['highest_price'] * (1 - self.config['trade_management']['trailing_stop_distance'] / 100)
            print(f"   📈 TRAILING AKTİF: ${self.position['trailing_stop_price']:,.2f}")

        # Trailing güncelle
        if self.position['trailing_active']:
            new_trailing = self.position['highest_price'] * (1 - self.config['trade_management']['trailing_stop_distance'] / 100)
            if new_trailing > self.position['trailing_stop_price']:
                self.position['trailing_stop_price'] = new_trailing

        # Çıkış kontrolü
        exit_reason = None

        if current_price >= self.position['tp']:
            exit_reason = 'Take Profit'
        elif current_price <= self.position['sl']:
            exit_reason = 'Stop Loss'
        elif self.position['trailing_active'] and current_price <= self.position['trailing_stop_price']:
            exit_reason = 'Trailing Stop'

        if exit_reason:
            self.close_position(current_price, exit_reason)

    def close_position(self, exit_price, reason):
        """Pozisyon kapat"""
        if self.position is None:
            return

        profit = (exit_price - self.position['entry_price']) * self.position['remaining_qty']
        profit_pct = ((exit_price - self.position['entry_price']) / self.position['entry_price']) * 100

        self.capital += profit

        trade = {
            'entry_time': self.position['entry_time'],
            'exit_time': datetime.now(),
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'profit': profit,
            'profit_pct': profit_pct,
            'exit_reason': reason,
            'pattern': self.position['pattern'],
            'balance_after': self.capital,
        }

        self.trades.append(trade)

        emoji = "✅" if profit > 0 else "❌"
        print(f"\n{'='*80}")
        print(f"{emoji} POZİSYON KAPANDI")
        print(f"{'='*80}")
        print(f"   Sebep: {reason}")
        print(f"   Giriş: ${self.position['entry_price']:,.2f}")
        print(f"   Çıkış: ${exit_price:,.2f}")
        print(f"   Kar/Zarar: ${profit:+,.2f} ({profit_pct:+.2f}%)")
        print(f"   Sermaye: ${self.capital:,.2f}")
        print(f"{'='*80}\n")

        self.position = None

        # Log kaydet
        self.save_log()

    def save_log(self):
        """Trade log'u kaydet"""
        log_file = 'intraday_paper_log.json'

        data = {
            'strategy': self.config['name'],
            'timeframe': self.config['timeframe'],
            'symbol': self.symbol,
            'initial_capital': self.initial_capital,
            'current_capital': self.capital,
            'total_trades': len(self.trades),
            'trades': []
        }

        for t in self.trades:
            data['trades'].append({
                'entry_time': t['entry_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'exit_time': t['exit_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'entry_price': float(t['entry_price']),
                'exit_price': float(t['exit_price']),
                'profit': float(t['profit']),
                'profit_pct': float(t['profit_pct']),
                'exit_reason': t['exit_reason'],
                'pattern': t['pattern'],
                'balance_after': float(t['balance_after']),
            })

        with open(log_file, 'w') as f:
            json.dump(data, f, indent=2)

    def print_status(self, current_price, df):
        """Durum yazdır"""
        latest = df.iloc[-1]
        pattern = latest.get('fractal_pattern', 'Unknown')
        strength = latest.get('fractal_strength', 0)
        now = datetime.now().strftime('%H:%M:%S')

        print(f"\n{'─'*80}")
        print(f"📊 [{now}] BTC: ${current_price:,.2f} | Pattern: {pattern} ({strength:.1f})")

        if self.position:
            profit_pct = ((current_price - self.position['entry_price']) / self.position['entry_price']) * 100
            unrealized = (current_price - self.position['entry_price']) * self.position['remaining_qty']

            print(f"   🔵 AÇIK: Giriş ${self.position['entry_price']:,.2f} | P/L: ${unrealized:+,.2f} ({profit_pct:+.2f}%)")

            if self.position['trailing_active']:
                print(f"   📈 Trailing: ${self.position['trailing_stop_price']:,.2f}")
        else:
            print(f"   ⏸️  Pozisyon yok")

        if len(self.trades) > 0:
            winning = [t for t in self.trades if t['profit'] > 0]
            print(f"   📊 Trades: {len(self.trades)} | Win: {len(winning)} ({len(winning)/len(self.trades)*100:.0f}%) | ROI: {((self.capital/self.initial_capital-1)*100):+.2f}%")

        print(f"{'─'*80}")

    def run(self, check_interval=60):
        """Çalıştır"""

        print(f"\n🚀 INTRADAY PAPER TRADING BAŞLIYOR...")
        print(f"   Kontrol aralığı: {check_interval} saniye")
        print(f"   Ctrl+C ile durdurun\n")

        iteration = 0

        try:
            while True:
                iteration += 1

                # Veri çek
                df = self.fetch_candles(200)

                if df is None:
                    time.sleep(30)
                    continue

                # Analiz
                df = self.analyze(df)

                if df is None:
                    time.sleep(30)
                    continue

                # Güncel fiyat
                current_price = df.iloc[-1]['close']

                # Pozisyon yönetimi
                if self.position:
                    self.update_position(current_price)
                else:
                    # Giriş sinyali
                    signal = self.check_entry(df)

                    if signal['signal']:
                        print(f"\n🎯 GİRİŞ SİNYALİ! {signal['pattern']} ({signal['strength']:.1f})")
                        self.open_position(signal)

                # Durum
                self.print_status(current_price, df)

                # Bekle
                time.sleep(check_interval)

        except KeyboardInterrupt:
            print(f"\n\n🛑 DURDURULDU!")
            self.print_final_report()

    def print_final_report(self):
        """Final rapor"""
        print(f"\n{'='*80}")
        print("📊 INTRADAY PAPER TRADING RAPORU")
        print(f"{'='*80}")

        print(f"\n💰 SERMAYE:")
        print(f"   Başlangıç: ${self.initial_capital:,.2f}")
        print(f"   Bitiş: ${self.capital:,.2f}")
        print(f"   Kar/Zarar: ${self.capital - self.initial_capital:+,.2f}")
        print(f"   ROI: {((self.capital/self.initial_capital - 1)*100):+.2f}%")

        if len(self.trades) > 0:
            winning = [t for t in self.trades if t['profit'] > 0]
            losing = [t for t in self.trades if t['profit'] < 0]

            print(f"\n📊 İŞLEMLER:")
            print(f"   Toplam: {len(self.trades)}")
            print(f"   Kazanan: {len(winning)} ({len(winning)/len(self.trades)*100:.1f}%)")
            print(f"   Kaybeden: {len(losing)} ({len(losing)/len(self.trades)*100:.1f}%)")

            if winning:
                print(f"   Ort. Kazanç: ${np.mean([t['profit'] for t in winning]):+,.2f}")

            if losing:
                print(f"   Ort. Zarar: ${np.mean([t['profit'] for t in losing]):+,.2f}")

        print(f"\n📁 Log: intraday_paper_log.json")
        print(f"{'='*80}\n")


def main():
    print("\n" + "="*80)
    print("INTRADAY PAPER TRADING - 15M TIMEFRAME")
    print("="*80)
    print("""
⚡ GÜN İÇİ TRADİNG - Hızlı Giriş/Çıkış

Parametreler:
  - Timeframe: 15 dakika
  - TP: %2 (önceden %30!)
  - SL: %1 (önceden %8!)
  - Trailing: %1 / %0.5
  - Kontrol: Her 1 dakika

⚠️  PAPER TRADING - GERÇEK PARA RİSKİ YOK!
    """)

    symbol = input("Symbol (BTC/USDT): ").strip() or "BTC/USDT"
    capital = input("Sermaye (10000): ").strip() or "10000"
    capital = float(capital)

    confirm = input(f"\n✅ {symbol} ${capital:,.2f} ile başla? (y/n): ").lower()

    if confirm != 'y':
        print("İptal edildi.")
        return

    # Engine
    engine = IntradayPaperTrading(symbol=symbol, initial_capital=capital)

    # Çalıştır (her 1 dakika)
    engine.run(check_interval=60)


if __name__ == '__main__':
    main()
