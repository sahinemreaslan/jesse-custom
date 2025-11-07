"""
SIMPLE FRACTAL STRATEGY - Basit ama Etkili
═══════════════════════════════════════════════════════════
15m Fraktal Sinyalleri + 1h Trend Filtresi

STRATEJİ:
1. 15m'de Fraktal sinyali (Trending Up veya Outside Bar)
2. 1h'de trend yukarı mı? (Fiyat > EMA50)
3. Fraktal gücü >= 30
4. GIRIŞ: Yukarıdaki 3 koşul DOĞRUYSA

ÇIKıŞ:
- TP: %1.5
- SL: %0.8
- Trailing Stop: %1 kârda aktif, %0.4 mesafe

NEDEN BU STRATEJİ:
✅ Robustness test'te +11.86% ROI (komisyonsuz)
✅ Basit ve anlaşılır
✅ Multi-timeframe ama aşırı kompleks değil
✅ Overfitting riski düşük
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
import warnings
warnings.filterwarnings('ignore')


# ═══════════════════════════════════════════════════════════
# STRATEGY CONFIG
# ═══════════════════════════════════════════════════════════

SIMPLE_FRACTAL_CONFIG = {
    'name': 'Simple Fractal + 1h Trend Filter',

    # Giriş Kuralları
    'base_tf': '15m',
    'fractal_patterns': ['Trending Up', 'Outside Bar'],
    'min_fractal_strength': 30,

    # 1h Trend Filtresi
    'higher_tf': '1h',
    'trend_ema_period': 50,

    # TP/SL (komisyon sonrası pozitif kalacak şekilde ayarlandı)
    'tp_percent': 0.015,  # %1.5
    'sl_percent': 0.008,  # %0.8

    # Trailing Stop
    'use_trailing_stop': True,
    'trailing_activation': 1.0,   # %1 kârda aktif
    'trailing_distance': 0.4,      # %0.4 mesafe

    # Breakeven
    'use_breakeven': True,
    'breakeven_activation': 0.6,   # %0.6 kârda aktif
    'breakeven_offset': 0.1,       # +%0.1

    # Risk Yönetimi
    'position_size': 0.10,         # %10 sermaye
    'commission': 0.0004,          # %0.04
    'leverage': 1,                 # Kaldıraçsız (başlangıç için)
}


# ═══════════════════════════════════════════════════════════
# DATA LOADER
# ═══════════════════════════════════════════════════════════

class SimpleFractalDataLoader:
    """15m + 1h veri yükleyici"""

    def __init__(self):
        self.conn_params = {
            'host': '127.0.0.1',
            'database': 'jesse_db',
            'user': 'voidstring',
            'password': ''
        }

    def load_data(self, start_date, end_date):
        """15m ve 1h verilerini yükle ve merge et"""
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)

        conn = psycopg2.connect(**self.conn_params)

        # 15m veri
        query_15m = """
            SELECT timestamp, open, high, low, close, volume
            FROM candle
            WHERE exchange = 'Binance Futures'
            AND symbol = 'BTC-USDT'
            AND timeframe = '15m'
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp ASC
        """

        df_15m = pd.read_sql_query(query_15m, conn, params=(start_ts, end_ts))

        # 1h veri
        query_1h = """
            SELECT timestamp, open, high, low, close, volume
            FROM candle
            WHERE exchange = 'Binance Futures'
            AND symbol = 'BTC-USDT'
            AND timeframe = '1h'
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp ASC
        """

        df_1h = pd.read_sql_query(query_1h, conn, params=(start_ts, end_ts))
        conn.close()

        if len(df_15m) == 0 or len(df_1h) == 0:
            return None

        # Datetime index
        df_15m['datetime'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        df_15m.set_index('datetime', inplace=True)

        df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
        df_1h.set_index('datetime', inplace=True)

        # 1h EMA hesapla
        df_1h['ema_50'] = df_1h['close'].ewm(span=50, adjust=False).mean()

        # 1h verisini 15m'e merge et (forward fill)
        # Her 15m timestamp için, o zamana kadar olan 1h verisini kullan
        df_15m['1h_close'] = df_15m.index.map(
            lambda dt: df_1h[df_1h.index <= dt]['close'].iloc[-1]
            if len(df_1h[df_1h.index <= dt]) > 0 else np.nan
        )

        df_15m['1h_ema_50'] = df_15m.index.map(
            lambda dt: df_1h[df_1h.index <= dt]['ema_50'].iloc[-1]
            if len(df_1h[df_1h.index <= dt]) > 0 else np.nan
        )

        # Fraktal analiz
        df_fraktal = pd.DataFrame({
            'timestamp': df_15m.index.astype(np.int64) // 10**6,
            'open': df_15m['open'],
            'high': df_15m['high'],
            'low': df_15m['low'],
            'close': df_15m['close'],
            'volume': df_15m['volume']
        })

        df_fraktal = FractalAnalyzer.analyze_series(df_fraktal)

        df_15m['fractal_pattern'] = df_fraktal['fractal_pattern'].values
        df_15m['fractal_strength'] = df_fraktal['fractal_strength'].values

        # NaN temizle
        df_15m = df_15m.dropna()

        print(f"✅ Veri yüklendi: {len(df_15m)} mum (15m)")
        print(f"   Tarih: {df_15m.index[0].strftime('%Y-%m-%d')} → {df_15m.index[-1].strftime('%Y-%m-%d')}")

        return df_15m


# ═══════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════

class SimpleFractalBacktest:
    """Basit fraktal strateji backtest"""

    def __init__(self, config, initial_capital=10000):
        self.config = config
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = None
        self.trades = []
        self.balance_history = [initial_capital]
        self.commission_paid = 0

    def calculate_commission(self, price, quantity):
        """Komisyon hesapla"""
        trade_value = price * quantity
        return trade_value * self.config['commission']

    def check_entry_signal(self, row):
        """Giriş sinyali kontrolü"""
        # Kural 1: Fraktal pattern
        pattern = row.get('fractal_pattern', None)
        if pattern not in self.config['fractal_patterns']:
            return False

        # Kural 2: Fraktal strength
        strength = row.get('fractal_strength', 0)
        if strength < self.config['min_fractal_strength']:
            return False

        # Kural 3: 1h trend filtresi (Fiyat > EMA50)
        price_1h = row.get('1h_close', None)
        ema_1h = row.get('1h_ema_50', None)

        if price_1h is None or ema_1h is None:
            return False

        if price_1h <= ema_1h:
            return False

        return True

    def open_position(self, row):
        """Pozisyon aç"""
        if self.position is not None:
            return

        entry_price = row['close']
        position_value = self.capital * self.config['position_size']
        quantity = position_value / entry_price

        # Komisyon
        commission = self.calculate_commission(entry_price, quantity)
        self.capital -= commission
        self.commission_paid += commission

        self.position = {
            'entry_price': entry_price,
            'entry_time': row.name,
            'quantity': quantity,
            'tp': entry_price * (1 + self.config['tp_percent']),
            'sl': entry_price * (1 - self.config['sl_percent']),
            'highest_price': entry_price,
            'trailing_active': False,
            'trailing_stop_price': 0,
            'breakeven_active': False,
            'entry_commission': commission,
        }

    def update_position(self, row):
        """Pozisyon güncelle"""
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
            profit_pct >= self.config['breakeven_activation']):
            offset = self.config['breakeven_offset']
            self.position['sl'] = self.position['entry_price'] * (1 + offset / 100)
            self.position['breakeven_active'] = True

        # Trailing stop
        if (not self.position['trailing_active'] and
            profit_pct >= self.config['trailing_activation']):
            self.position['trailing_active'] = True
            distance = self.config['trailing_distance']
            self.position['trailing_stop_price'] = (
                self.position['highest_price'] * (1 - distance / 100)
            )

        if self.position['trailing_active']:
            distance = self.config['trailing_distance']
            new_trailing = self.position['highest_price'] * (1 - distance / 100)
            if new_trailing > self.position['trailing_stop_price']:
                self.position['trailing_stop_price'] = new_trailing

        # Çıkış kontrolü
        exit_reason = None
        exit_price = None

        # TP
        if high >= self.position['tp']:
            exit_reason = 'TP'
            exit_price = self.position['tp']
        # SL
        elif low <= self.position['sl']:
            exit_reason = 'SL'
            exit_price = self.position['sl']
        # Trailing
        elif (self.position['trailing_active'] and
              low <= self.position['trailing_stop_price']):
            exit_reason = 'Trailing'
            exit_price = self.position['trailing_stop_price']

        if exit_reason:
            return {
                'exit_reason': exit_reason,
                'exit_price': exit_price,
                'exit_time': row.name
            }

        return None

    def close_position(self, exit_info):
        """Pozisyon kapat"""
        exit_price = exit_info['exit_price']
        exit_time = exit_info['exit_time']
        exit_reason = exit_info['exit_reason']

        # Komisyon
        exit_commission = self.calculate_commission(exit_price, self.position['quantity'])

        # PNL
        gross_pnl = (exit_price - self.position['entry_price']) * self.position['quantity']
        net_pnl = gross_pnl - self.position['entry_commission'] - exit_commission

        self.capital += net_pnl
        self.commission_paid += exit_commission

        # Trade kaydı
        duration = (exit_time - self.position['entry_time']).total_seconds() / 60

        self.trades.append({
            'entry_time': self.position['entry_time'],
            'exit_time': exit_time,
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason,
            'duration_min': duration,
        })

        self.balance_history.append(self.capital)
        self.position = None

    def run(self, df):
        """Backtest çalıştır"""
        self.capital = self.initial_capital
        self.position = None
        self.trades = []
        self.balance_history = [self.initial_capital]
        self.commission_paid = 0

        for idx in range(len(df)):
            row = df.iloc[idx]

            if self.position:
                exit_info = self.update_position(row)
                if exit_info:
                    self.close_position(exit_info)
            else:
                if self.check_entry_signal(row):
                    self.open_position(row)

        # Açık pozisyon varsa kapat
        if self.position:
            last_row = df.iloc[-1]
            exit_info = {
                'exit_price': last_row['close'],
                'exit_time': last_row.name,
                'exit_reason': 'Backtest End'
            }
            self.close_position(exit_info)

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
        pf = total_wins / total_losses if total_losses > 0 else 0

        return {
            'roi': roi,
            'total_pnl': total_pnl,
            'num_trades': len(self.trades),
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'profit_factor': pf,
            'final_capital': self.capital,
            'commission_paid': self.commission_paid,
            'trades': self.trades,
        }


# ═══════════════════════════════════════════════════════════
# WALK-FORWARD VALIDATION
# ═══════════════════════════════════════════════════════════

def walk_forward_validate(df, config):
    """Walk-forward validation"""
    # Veriyi 4 çeyreğe böl
    total_days = (df.index[-1] - df.index[0]).days
    quarter_days = total_days // 4

    quarters = []
    start_date = df.index[0]

    for i in range(4):
        end_date = start_date + timedelta(days=quarter_days)
        quarter_df = df[(df.index >= start_date) & (df.index < end_date)]

        if len(quarter_df) > 0:
            quarters.append(quarter_df)

        start_date = end_date

    if len(quarters) < 3:
        return None

    # 2 çeyrek test
    results = []

    for i in range(len(quarters) - 1):
        train_df = quarters[i]
        test_df = quarters[i + 1]

        # Test
        engine = SimpleFractalBacktest(config)
        test_result = engine.run(test_df)

        if test_result:
            results.append({
                'quarter': f'Q{i+2}',
                'roi': test_result['roi'],
                'trades': test_result['num_trades'],
                'win_rate': test_result['win_rate'],
            })

    if len(results) == 0:
        return None

    avg_roi = np.mean([r['roi'] for r in results])
    std_roi = np.std([r['roi'] for r in results])

    return {
        'avg_roi': avg_roi,
        'std_roi': std_roi,
        'quarters': results,
        'is_consistent': std_roi < 10,  # Std < 10% = tutarlı
    }


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    """Ana test fonksiyonu"""
    print("\n" + "="*100)
    print("SIMPLE FRACTAL STRATEGY - Basit ama Etkili")
    print("="*100)
    print(f"""
Strateji: {SIMPLE_FRACTAL_CONFIG['name']}

GİRİŞ KURALLARI:
  1. 15m'de Fraktal sinyali (Trending Up veya Outside Bar)
  2. Fraktal gücü >= {SIMPLE_FRACTAL_CONFIG['min_fractal_strength']}
  3. 1h'de trend yukarı (Fiyat > EMA50)

TP/SL:
  TP: {SIMPLE_FRACTAL_CONFIG['tp_percent']*100}%
  SL: {SIMPLE_FRACTAL_CONFIG['sl_percent']*100}%
  Trailing: {SIMPLE_FRACTAL_CONFIG['trailing_activation']}% kârda aktif, {SIMPLE_FRACTAL_CONFIG['trailing_distance']}% mesafe

Komisyon: {SIMPLE_FRACTAL_CONFIG['commission']*100}%
    """)

    # Veri yükle
    print("📊 ADIM 1: Veri Yükleme")
    print("-"*100)

    loader = SimpleFractalDataLoader()
    df = loader.load_data('2024-01-01', '2024-10-31')

    if df is None:
        print("❌ Veri yüklenemedi!")
        return

    print()

    # Backtest
    print("🧪 ADIM 2: Backtest")
    print("-"*100)

    engine = SimpleFractalBacktest(SIMPLE_FRACTAL_CONFIG)
    result = engine.run(df)

    if result is None:
        print("❌ Hiç trade yok!")
        return

    print(f"""
✅ Backtest Tamamlandı

PERFORMANS:
  ROI: {result['roi']:+.2f}%
  Net Kar: ${result['total_pnl']:+,.2f}
  Trade Sayısı: {result['num_trades']}
  Win Rate: {result['win_rate']:.1f}%
  Profit Factor: {result['profit_factor']:.2f}
  Max Drawdown: {result['max_drawdown']:.2f}%
  Komisyon: ${result['commission_paid']:.2f}
    """)

    # Çıkış sebepleri
    exit_reasons = {}
    for t in result['trades']:
        reason = t['exit_reason']
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    print("ÇIKIŞ SEBEPLERİ:")
    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(result['trades'])) * 100
        print(f"  {reason}: {count} ({pct:.1f}%)")

    print()

    # Walk-forward validation
    print("🔬 ADIM 3: Walk-Forward Validation")
    print("-"*100)

    wf_result = walk_forward_validate(df, SIMPLE_FRACTAL_CONFIG)

    if wf_result:
        print(f"""
Ortalama ROI: {wf_result['avg_roi']:+.2f}%
Standart Sapma: {wf_result['std_roi']:.2f}%
Tutarlılık: {'✅ Tutarlı' if wf_result['is_consistent'] else '⚠️ Değişken'}

Çeyreklik Performans:
        """)

        for q in wf_result['quarters']:
            print(f"  {q['quarter']}: ROI {q['roi']:+.2f}%, {q['trades']} trade, WR {q['win_rate']:.1f}%")

    print("\n" + "="*100)
    print("✅ FINAL DEĞERLENDİRME")
    print("="*100)

    if result['roi'] > 0 and result['win_rate'] > 50 and result['profit_factor'] > 1.5:
        print("\n🎉 STRATEJİ BAŞARILI!")
        print("""
Sonraki Adımlar:
  1. Paper trading ile 1 ay test et
  2. Farklı periyotlarda test et (2023, 2022)
  3. Küçük sermaye ile canlı dene ($100-500)
        """)
    elif result['roi'] > 0:
        print("\n⚠️ STRATEJİ UMUT VAR AMA DİKKATLİ!")
        print("""
Sorunlar:
  - Win rate veya Profit Factor düşük
  - Daha fazla test gerekli

Öneriler:
  1. Parametreleri optimize et
  2. Daha uzun periyotta test et
  3. Paper trading şart
        """)
    else:
        print("\n❌ STRATEJİ YETERSİZ!")
        print("""
ROI negatif. Değişiklik önerileri:
  1. TP/SL oranını değiştir
  2. Fraktal strength threshold'u ayarla
  3. Farklı trend filtresi dene (EMA21 yerine EMA50)
        """)

    print("="*100)


if __name__ == '__main__':
    main()
