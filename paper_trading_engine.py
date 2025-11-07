"""
PAPER TRADING ENGINE - Trailing Stop Master
═══════════════════════════════════════════════════════════
Gerçek zamanlı piyasada Trailing Stop Master stratejisini
paper trading ile test et. Para riski SIFIR!

Özellikler:
  - Binance'den canlı 1h mum verisi
  - Otomatik sinyal tespiti
  - Otomatik pozisyon açma/kapama
  - Trailing stop yönetimi
  - Trade log ve performans raporu
  - Gerçek zamanlı monitoring

Kullanım:
  python paper_trading_engine.py

Not: Para riski YOK, sadece simülasyon!
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import ccxt
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime, timedelta
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer


# TRAILING STOP MASTER STRATEJİSİ (OPTİMİZE PARAMETRELERİ)
STRATEGY_CONFIG = {
    'name': 'Trailing Stop Master (Optimized)',
    'entry_patterns': ['Trending Up', 'Outside Bar'],
    'min_strength': 30,
    'position_size': 0.15,
    'tp_percent': 0.30,
    'sl_percent': 0.08,
    'weights': {
        'TRENDING_UP': 3.0,
        'OUTSIDE_BAR': 3.5,
        'TRENDING_DOWN': 2.0,
        'INSIDE_BAR': 0.3
    },
    'trailing_stop_activation': 0.05,
    'trailing_stop_distance': 0.035,
    'breakeven_activation': 0.03,
    'breakeven_offset': 0.005,
}


class PaperTradingEngine:
    """Paper trading engine"""

    def __init__(self, symbol='BTC/USDT', initial_capital=10000):
        """Initialize"""
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.capital = initial_capital

        # Exchange
        self.exchange = ccxt.binance({'enableRateLimit': True})

        # Pozisyon
        self.position = None

        # Trade history
        self.trades = []

        # Performans tracking
        self.equity_curve = [initial_capital]
        self.timestamps = [datetime.now()]

        print("="*80)
        print("PAPER TRADING ENGINE - TRAILING STOP MASTER")
        print("="*80)
        print(f"\n💰 Başlangıç Sermayesi: ${initial_capital:,.2f}")
        print(f"📊 Symbol: {symbol}")
        print(f"⚙️  Strateji: {STRATEGY_CONFIG['name']}")
        print("\n⚠️  BU PAPER TRADING - GERÇEK PARA RİSKİ YOK!")
        print("="*80)

    def fetch_recent_candles(self, limit=200):
        """Son X saatlik mum verilerini çek"""
        try:
            candles = self.exchange.fetch_ohlcv(
                self.symbol,
                timeframe='1h',
                limit=limit
            )

            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df

        except Exception as e:
            print(f"⚠️  Veri çekme hatası: {e}")
            return None

    def analyze_market(self, df):
        """Piyasa analizini yap"""
        if len(df) < 50:
            return None

        # Fraktal analiz
        df = FractalAnalyzer.analyze_series(df)
        analyzer = MultiTimeframeFractalAnalyzer(weights=STRATEGY_CONFIG['weights'])
        df = analyzer.calculate_fractal_score(df)

        return df

    def check_entry_signal(self, df):
        """Giriş sinyali kontrolü"""
        latest = df.iloc[-1]

        pattern = latest.get('fractal_pattern', 'Unknown')
        strength = latest.get('fractal_strength', 0)
        price = latest['close']

        # Sinyal var mı?
        if pattern in STRATEGY_CONFIG['entry_patterns'] and strength >= STRATEGY_CONFIG['min_strength']:
            return {
                'signal': True,
                'pattern': pattern,
                'strength': strength,
                'price': price,
                'timestamp': datetime.fromtimestamp(latest['timestamp'] / 1000)
            }

        return {'signal': False}

    def open_position(self, signal):
        """Pozisyon aç (PAPER)"""
        if self.position is not None:
            return False

        entry_price = signal['price']
        position_size_usd = self.capital * STRATEGY_CONFIG['position_size']
        quantity = position_size_usd / entry_price

        self.position = {
            'entry_time': signal['timestamp'],
            'entry_price': entry_price,
            'quantity': quantity,
            'position_size_usd': position_size_usd,
            'pattern': signal['pattern'],
            'strength': signal['strength'],
            'tp_price': entry_price * (1 + STRATEGY_CONFIG['tp_percent']),
            'sl_price': entry_price * (1 - STRATEGY_CONFIG['sl_percent']),
            'trailing_stop_price': 0,
            'breakeven_active': False,
            'trailing_active': False,
            'highest_price': entry_price,
        }

        print(f"\n{'='*80}")
        print(f"🚀 YENİ POZİSYON AÇILDI (PAPER)")
        print(f"{'='*80}")
        print(f"   Zaman: {signal['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Fiyat: ${entry_price:,.2f}")
        print(f"   Miktar: {quantity:.6f} {self.symbol.split('/')[0]}")
        print(f"   Pozisyon: ${position_size_usd:,.2f}")
        print(f"   Pattern: {signal['pattern']} (Strength: {signal['strength']:.1f})")
        print(f"\n   📊 SEVİYELER:")
        print(f"      Take Profit: ${self.position['tp_price']:,.2f} (+{STRATEGY_CONFIG['tp_percent']*100:.1f}%)")
        print(f"      Stop Loss: ${self.position['sl_price']:,.2f} (-{STRATEGY_CONFIG['sl_percent']*100:.1f}%)")
        print(f"      Trailing: {STRATEGY_CONFIG['trailing_stop_activation']*100:.1f}% aktivasyon")
        print(f"{'='*80}\n")

        return True

    def update_position(self, current_price):
        """Pozisyonu güncelle"""
        if self.position is None:
            return

        # Highest price güncelle
        if current_price > self.position['highest_price']:
            self.position['highest_price'] = current_price

        # Kar/zarar hesapla
        profit_pct = ((current_price - self.position['entry_price']) / self.position['entry_price']) * 100

        # Breakeven kontrolü
        if not self.position['breakeven_active'] and profit_pct >= STRATEGY_CONFIG['breakeven_activation'] * 100:
            self.position['sl_price'] = self.position['entry_price'] * (1 + STRATEGY_CONFIG['breakeven_offset'])
            self.position['breakeven_active'] = True
            print(f"   🛡️  BREAKEVEN AKTİF: SL → ${self.position['sl_price']:,.2f}")

        # Trailing stop kontrolü
        if not self.position['trailing_active'] and profit_pct >= STRATEGY_CONFIG['trailing_stop_activation'] * 100:
            self.position['trailing_active'] = True
            self.position['trailing_stop_price'] = self.position['highest_price'] * (1 - STRATEGY_CONFIG['trailing_stop_distance'])
            print(f"   📈 TRAİLİNG STOP AKTİF: ${self.position['trailing_stop_price']:,.2f}")

        # Trailing stop güncelle
        if self.position['trailing_active']:
            new_trailing = self.position['highest_price'] * (1 - STRATEGY_CONFIG['trailing_stop_distance'])
            if new_trailing > self.position['trailing_stop_price']:
                self.position['trailing_stop_price'] = new_trailing
                print(f"   📊 Trailing güncellendi: ${self.position['trailing_stop_price']:,.2f} (Kar: +{profit_pct:.2f}%)")

        # Çıkış kontrolü
        exit_reason = None

        # Take Profit
        if current_price >= self.position['tp_price']:
            exit_reason = 'Take Profit'

        # Stop Loss
        elif current_price <= self.position['sl_price']:
            exit_reason = 'Stop Loss'

        # Trailing Stop
        elif self.position['trailing_active'] and current_price <= self.position['trailing_stop_price']:
            exit_reason = 'Trailing Stop'

        if exit_reason:
            self.close_position(current_price, exit_reason)

    def close_position(self, exit_price, reason):
        """Pozisyonu kapat"""
        if self.position is None:
            return

        # Kar/zarar hesapla
        profit = (exit_price - self.position['entry_price']) * self.position['quantity']
        profit_pct = ((exit_price - self.position['entry_price']) / self.position['entry_price']) * 100

        # Sermayeyi güncelle
        self.capital += profit

        # Trade kaydet
        trade = {
            'entry_time': self.position['entry_time'],
            'exit_time': datetime.now(),
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'quantity': self.position['quantity'],
            'profit': profit,
            'profit_pct': profit_pct,
            'exit_reason': reason,
            'pattern': self.position['pattern'],
            'balance_after': self.capital,
        }

        self.trades.append(trade)

        # Ekrana yazdır
        emoji = "✅" if profit > 0 else "❌"
        print(f"\n{'='*80}")
        print(f"{emoji} POZİSYON KAPANDI (PAPER)")
        print(f"{'='*80}")
        print(f"   Çıkış: {reason}")
        print(f"   Giriş: ${self.position['entry_price']:,.2f} ({self.position['entry_time'].strftime('%Y-%m-%d %H:%M')})")
        print(f"   Çıkış: ${exit_price:,.2f} ({trade['exit_time'].strftime('%Y-%m-%d %H:%M')})")
        print(f"   Kar/Zarar: ${profit:+,.2f} ({profit_pct:+.2f}%)")
        print(f"   Yeni Sermaye: ${self.capital:,.2f}")
        print(f"{'='*80}\n")

        # Pozisyonu temizle
        self.position = None

        # Trade log'u kaydet
        self.save_trade_log()

    def save_trade_log(self):
        """Trade geçmişini kaydet"""
        log_file = 'paper_trading_log.json'

        data = {
            'strategy': STRATEGY_CONFIG['name'],
            'symbol': self.symbol,
            'initial_capital': self.initial_capital,
            'current_capital': self.capital,
            'total_trades': len(self.trades),
            'trades': []
        }

        for trade in self.trades:
            data['trades'].append({
                'entry_time': trade['entry_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'exit_time': trade['exit_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'entry_price': float(trade['entry_price']),
                'exit_price': float(trade['exit_price']),
                'quantity': float(trade['quantity']),
                'profit': float(trade['profit']),
                'profit_pct': float(trade['profit_pct']),
                'exit_reason': trade['exit_reason'],
                'pattern': trade['pattern'],
                'balance_after': float(trade['balance_after']),
            })

        with open(log_file, 'w') as f:
            json.dump(data, f, indent=2)

    def print_status(self, current_price, df):
        """Mevcut durumu yazdır"""
        latest = df.iloc[-1]
        pattern = latest.get('fractal_pattern', 'Unknown')
        strength = latest.get('fractal_strength', 0)

        print(f"\n{'─'*80}")
        print(f"📊 DURUM: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'─'*80}")
        print(f"   Fiyat: ${current_price:,.2f}")
        print(f"   Pattern: {pattern} (Strength: {strength:.1f})")
        print(f"   Sermaye: ${self.capital:,.2f} (ROI: {((self.capital/self.initial_capital - 1)*100):+.2f}%)")
        print(f"   Toplam Trade: {len(self.trades)}")

        if self.position:
            profit_pct = ((current_price - self.position['entry_price']) / self.position['entry_price']) * 100
            unrealized = (current_price - self.position['entry_price']) * self.position['quantity']

            print(f"\n   🔵 AÇIK POZİSYON:")
            print(f"      Giriş: ${self.position['entry_price']:,.2f}")
            print(f"      Mevcut: ${current_price:,.2f}")
            print(f"      Kar/Zarar: ${unrealized:+,.2f} ({profit_pct:+.2f}%)")
            print(f"      TP: ${self.position['tp_price']:,.2f}")
            print(f"      SL: ${self.position['sl_price']:,.2f}")

            if self.position['trailing_active']:
                print(f"      Trailing: ${self.position['trailing_stop_price']:,.2f} ✅")
        else:
            print(f"\n   ⏸️  Pozisyon yok - Sinyal bekleniyor...")

        print(f"{'─'*80}\n")

    def run(self, check_interval=3600):
        """Paper trading çalıştır"""

        print(f"\n🚀 PAPER TRADING BAŞLIYOR...")
        print(f"   Kontrol aralığı: {check_interval} saniye ({check_interval/60:.0f} dakika)")
        print(f"   Ctrl+C ile durdurun\n")

        iteration = 0

        try:
            while True:
                iteration += 1

                print(f"\n{'='*80}")
                print(f"🔄 İTERASYON #{iteration}")
                print(f"{'='*80}")

                # 1. Veri çek
                print("⏳ Veri çekiliyor...")
                df = self.fetch_recent_candles(200)

                if df is None:
                    print("⚠️  Veri çekilemedi, tekrar denenecek...")
                    time.sleep(60)
                    continue

                # 2. Analiz yap
                print("⏳ Fraktal analiz yapılıyor...")
                df = self.analyze_market(df)

                if df is None:
                    print("⚠️  Analiz başarısız, tekrar denenecek...")
                    time.sleep(60)
                    continue

                # 3. Güncel fiyat
                current_price = df.iloc[-1]['close']

                # 4. Pozisyon var mı?
                if self.position:
                    # Pozisyonu güncelle
                    self.update_position(current_price)
                else:
                    # Yeni sinyal kontrolü
                    signal = self.check_entry_signal(df)

                    if signal['signal']:
                        print(f"\n🎯 GİRİŞ SİNYALİ TESPİT EDİLDİ!")
                        print(f"   Pattern: {signal['pattern']}")
                        print(f"   Strength: {signal['strength']:.1f}")
                        self.open_position(signal)

                # 5. Durum raporu
                self.print_status(current_price, df)

                # 6. Performans özeti
                if len(self.trades) > 0:
                    winning = [t for t in self.trades if t['profit'] > 0]
                    win_rate = len(winning) / len(self.trades) * 100

                    print(f"📊 PERFORMANS ÖZETİ:")
                    print(f"   Toplam Trade: {len(self.trades)}")
                    print(f"   Kazanan: {len(winning)} ({win_rate:.1f}%)")
                    print(f"   ROI: {((self.capital/self.initial_capital - 1)*100):+.2f}%")

                # 7. Bekle
                print(f"\n⏳ Sonraki kontrol: {check_interval} saniye ({check_interval/60:.0f} dakika) sonra...")
                print(f"   (Ctrl+C ile durdurun)")

                time.sleep(check_interval)

        except KeyboardInterrupt:
            print(f"\n\n{'='*80}")
            print("🛑 PAPER TRADING DURDURULDU")
            print(f"{'='*80}")

            self.print_final_report()

    def print_final_report(self):
        """Final raporu"""

        print(f"\n{'='*80}")
        print("📊 PAPER TRADING FINAL RAPORU")
        print(f"{'='*80}")

        print(f"\n💰 SERMAYE:")
        print(f"   Başlangıç: ${self.initial_capital:,.2f}")
        print(f"   Bitiş: ${self.capital:,.2f}")
        print(f"   Kar/Zarar: ${self.capital - self.initial_capital:+,.2f}")
        print(f"   ROI: {((self.capital/self.initial_capital - 1)*100):+.2f}%")

        if len(self.trades) > 0:
            winning = [t for t in self.trades if t['profit'] > 0]
            losing = [t for t in self.trades if t['profit'] < 0]

            print(f"\n📊 İŞLEM İSTATİSTİKLERİ:")
            print(f"   Toplam: {len(self.trades)}")
            print(f"   Kazanan: {len(winning)} ({len(winning)/len(self.trades)*100:.1f}%)")
            print(f"   Kaybeden: {len(losing)} ({len(losing)/len(self.trades)*100:.1f}%)")

            if winning:
                avg_win = np.mean([t['profit'] for t in winning])
                print(f"   Ort. Kazanç: ${avg_win:+,.2f}")

            if losing:
                avg_loss = np.mean([t['profit'] for t in losing])
                print(f"   Ort. Zarar: ${avg_loss:+,.2f}")

            # Çıkış sebepleri
            exit_reasons = {}
            for t in self.trades:
                reason = t['exit_reason']
                exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

            print(f"\n🎯 ÇIKIŞ SEBEPLERİ:")
            for reason, count in exit_reasons.items():
                pct = (count / len(self.trades)) * 100
                print(f"   {reason:20} → {count} ({pct:.1f}%)")

        print(f"\n📁 Trade log kaydedildi: paper_trading_log.json")
        print(f"\n{'='*80}\n")


def main():
    """Ana fonksiyon"""

    print("\n" + "="*80)
    print("PAPER TRADING - TRAILING STOP MASTER")
    print("="*80)
    print("""
Bu script gerçek zamanlı piyasada Trailing Stop Master stratejisini
paper trading ile test eder.

⚠️  ÖNEMLİ:
   - Gerçek para riski YOK!
   - Sadece simülasyon
   - Her saatte bir kontrol edilir
   - Ctrl+C ile durdurun
    """)

    # Kullanıcı onayı
    symbol = input("Symbol (varsayılan: BTC/USDT): ").strip() or "BTC/USDT"
    capital = input("Başlangıç sermayesi (varsayılan: 10000): ").strip() or "10000"
    capital = float(capital)

    confirm = input(f"\n{symbol} için ${capital:,.2f} ile başlansın mı? (y/n): ").lower()

    if confirm != 'y':
        print("İptal edildi.")
        return

    # Engine başlat
    engine = PaperTradingEngine(symbol=symbol, initial_capital=capital)

    # Çalıştır (her saat kontrol)
    engine.run(check_interval=3600)  # 3600 saniye = 1 saat


if __name__ == '__main__':
    main()
