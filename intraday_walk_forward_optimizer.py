"""
INTRADAY WALK-FORWARD OPTIMIZER
═══════════════════════════════════════════════════════════
15 dakikalık timeframe için walk-forward optimizasyon
2 çeyrek train → 2 çeyrek test, 4 farklı window
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from intraday_strategy_config import INTRADAY_CONFIG
from itertools import product


class IntradayWalkForwardOptimizer:
    """Walk-forward optimizer for intraday strategy"""

    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.base_config = INTRADAY_CONFIG

        print("="*80)
        print("INTRADAY WALK-FORWARD OPTIMIZER")
        print("="*80)
        print("\nYöntem:")
        print("  - 2 yıllık veri → 8 çeyrek")
        print("  - Her döngü: 2 çeyrek train → 2 çeyrek test")
        print("  - 4 farklı window test edilecek")
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

        if len(df) == 0:
            print("❌ Veri bulunamadı!")
            return None

        print(f"✅ {len(df)} mum yüklendi")
        print(f"   Başlangıç: {datetime.fromtimestamp(df.iloc[0]['timestamp']/1000).strftime('%Y-%m-%d')}")
        print(f"   Bitiş: {datetime.fromtimestamp(df.iloc[-1]['timestamp']/1000).strftime('%Y-%m-%d')}")

        # Tarihleri ekle
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')

        return df

    def split_into_quarters(self, df):
        """Veriyi çeyreklere böl"""
        print("\n⏳ Veri çeyreklere bölünüyor...")

        min_date = df['date'].min()
        max_date = df['date'].max()

        # Her çeyrek yaklaşık 3 ay (91 gün)
        quarter_days = 91
        quarters = []

        current_date = min_date
        quarter_num = 1

        while current_date < max_date:
            quarter_end = current_date + timedelta(days=quarter_days)

            quarter_data = df[(df['date'] >= current_date) & (df['date'] < quarter_end)].copy()

            if len(quarter_data) > 0:
                quarters.append({
                    'num': quarter_num,
                    'start': current_date,
                    'end': quarter_end,
                    'data': quarter_data
                })

                print(f"   Q{quarter_num}: {current_date.strftime('%Y-%m-%d')} → {quarter_end.strftime('%Y-%m-%d')} ({len(quarter_data)} mum)")

                quarter_num += 1

            current_date = quarter_end

        print(f"\n✅ {len(quarters)} çeyrek oluşturuldu\n")

        return quarters

    def create_windows(self, quarters):
        """Walk-forward windows oluştur"""
        windows = []

        # 4 farklı window
        for i in range(len(quarters) - 3):
            train_quarters = [quarters[i], quarters[i+1]]
            test_quarters = [quarters[i+2], quarters[i+3]]

            train_data = pd.concat([q['data'] for q in train_quarters])
            test_data = pd.concat([q['data'] for q in test_quarters])

            windows.append({
                'name': f"W{i+1}",
                'train_quarters': [q['num'] for q in train_quarters],
                'test_quarters': [q['num'] for q in test_quarters],
                'train_data': train_data,
                'test_data': test_data
            })

        return windows

    def get_parameter_combinations(self):
        """Test edilecek parametre kombinasyonları"""
        # Detaylı grid (daha iyi sonuç için)
        params = {
            'min_strength': [20, 30, 40],
            'tp_percent': [0.01, 0.015, 0.02],  # %1, %1.5, %2
            'sl_percent': [0.005, 0.01, 0.015],  # %0.5, %1, %1.5
            'trailing_activation': [0.5, 1.0, 1.5],  # %0.5, %1, %1.5
            'trailing_distance': [0.3, 0.5, 0.7],  # %0.3, %0.5, %0.7
        }

        # Grid search: 3×3×3×3×3 = 243 kombinasyon
        combinations = list(product(
            params['min_strength'],
            params['tp_percent'],
            params['sl_percent'],
            params['trailing_activation'],
            params['trailing_distance']
        ))

        print(f"   Parametre aralıkları:")
        print(f"      min_strength: {params['min_strength']}")
        print(f"      TP: {[f'{x*100:.1f}%' for x in params['tp_percent']]}")
        print(f"      SL: {[f'{x*100:.1f}%' for x in params['sl_percent']]}")
        print(f"      Trailing Activation: {[f'{x:.1f}%' for x in params['trailing_activation']]}")
        print(f"      Trailing Distance: {[f'{x:.1f}%' for x in params['trailing_distance']]}")

        return combinations

    def backtest(self, df, config, commission=0.0005):
        """Backtest yap (komisyon dahil)"""
        capital = self.initial_capital
        position = None
        trades = []

        # Komisyon: %0.05 (Binance futures maker+taker ortalama)

        # Fraktal analiz
        df = FractalAnalyzer.analyze_series(df.copy())
        analyzer = MultiTimeframeFractalAnalyzer(weights=config['weights'])
        df = analyzer.calculate_fractal_score(df)

        for idx in range(len(df)):
            row = df.iloc[idx]

            if position:
                # Pozisyon güncelle
                current_price = row['close']
                high = row['high']
                low = row['low']

                # Highest price
                if high > position['highest_price']:
                    position['highest_price'] = high

                profit_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100

                # Breakeven
                if not position['breakeven_active'] and profit_pct >= config['breakeven_activation']:
                    position['sl'] = position['entry_price'] * (1 + config['breakeven_offset'] / 100)
                    position['breakeven_active'] = True

                # Trailing
                if not position['trailing_active'] and profit_pct >= config['trailing_activation']:
                    position['trailing_active'] = True
                    position['trailing_stop_price'] = position['highest_price'] * (1 - config['trailing_distance'] / 100)

                if position['trailing_active']:
                    new_trailing = position['highest_price'] * (1 - config['trailing_distance'] / 100)
                    if new_trailing > position['trailing_stop_price']:
                        position['trailing_stop_price'] = new_trailing

                # Çıkış kontrolü
                exit_reason = None
                exit_price = None

                if high >= position['tp']:
                    exit_reason = 'TP'
                    exit_price = position['tp']
                elif low <= position['sl']:
                    exit_reason = 'SL'
                    exit_price = position['sl']
                elif position['trailing_active'] and low <= position['trailing_stop_price']:
                    exit_reason = 'TRAIL'
                    exit_price = position['trailing_stop_price']

                if exit_reason:
                    # Kar/zarar hesapla
                    profit = (exit_price - position['entry_price']) * position['qty']

                    # Komisyon düş (giriş + çıkış)
                    commission_entry = position['entry_price'] * position['qty'] * commission
                    commission_exit = exit_price * position['qty'] * commission
                    total_commission = commission_entry + commission_exit

                    # Net kar
                    net_profit = profit - total_commission
                    capital += net_profit

                    trades.append({
                        'profit': net_profit,
                        'profit_pct': ((exit_price - position['entry_price']) / position['entry_price']) * 100,
                        'commission': total_commission
                    })

                    position = None

            else:
                # Giriş kontrol
                pattern = row.get('fractal_pattern', 'Unknown')
                strength = row.get('fractal_strength', 0)

                if pattern in config['entry_patterns'] and strength >= config['min_strength']:
                    entry_price = row['close']
                    qty = (capital * config['position_size']) / entry_price

                    position = {
                        'entry_price': entry_price,
                        'qty': qty,
                        'tp': entry_price * (1 + config['tp_percent']),
                        'sl': entry_price * (1 - config['sl_percent']),
                        'highest_price': entry_price,
                        'breakeven_active': False,
                        'trailing_active': False,
                        'trailing_stop_price': 0,
                    }

        # Açık pozisyon varsa kapat
        if position:
            exit_price = df.iloc[-1]['close']
            profit = (exit_price - position['entry_price']) * position['qty']

            # Komisyon düş
            commission_entry = position['entry_price'] * position['qty'] * commission
            commission_exit = exit_price * position['qty'] * commission
            total_commission = commission_entry + commission_exit

            net_profit = profit - total_commission
            capital += net_profit

            trades.append({
                'profit': net_profit,
                'profit_pct': ((exit_price - position['entry_price']) / position['entry_price']) * 100,
                'commission': total_commission
            })

        # Sonuçlar
        roi = ((capital / self.initial_capital) - 1) * 100
        num_trades = len(trades)
        win_rate = len([t for t in trades if t['profit'] > 0]) / num_trades * 100 if num_trades > 0 else 0

        return {
            'roi': roi,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'final_capital': capital
        }

    def optimize_on_train(self, train_data, combinations):
        """Train data üzerinde en iyi parametreleri bul"""
        best_params = None
        best_roi = -float('inf')

        for combo in combinations:
            min_strength, tp, sl, trail_act, trail_dist = combo

            config = self.base_config.copy()
            config['min_strength'] = min_strength
            config['tp_percent'] = tp
            config['sl_percent'] = sl
            config['trailing_activation'] = trail_act
            config['trailing_distance'] = trail_dist
            config['breakeven_activation'] = trail_act * 0.5  # Trailing'in yarısı
            config['breakeven_offset'] = 0.1

            result = self.backtest(train_data, config)

            if result['roi'] > best_roi and result['num_trades'] >= 10:
                best_roi = result['roi']
                best_params = combo

        return best_params, best_roi

    def test_on_forward(self, test_data, params):
        """Test data üzerinde performans ölç"""
        min_strength, tp, sl, trail_act, trail_dist = params

        config = self.base_config.copy()
        config['min_strength'] = min_strength
        config['tp_percent'] = tp
        config['sl_percent'] = sl
        config['trailing_activation'] = trail_act
        config['trailing_distance'] = trail_dist
        config['breakeven_activation'] = trail_act * 0.5
        config['breakeven_offset'] = 0.1

        return self.backtest(test_data, config)

    def run(self):
        """Optimizasyon çalıştır"""
        # Veri yükle
        df = self.load_data()
        if df is None:
            return

        # Çeyreklere böl
        quarters = self.split_into_quarters(df)

        if len(quarters) < 4:
            print("❌ En az 4 çeyrek veri gerekli!")
            return

        # Windows oluştur
        windows = self.create_windows(quarters)

        print(f"✅ {len(windows)} walk-forward window oluşturuldu:")
        for w in windows:
            print(f"   {w['name']}: Q{w['train_quarters'][0]}-Q{w['train_quarters'][1]} train → Q{w['test_quarters'][0]}-Q{w['test_quarters'][1]} test")

        print()

        # Parametre kombinasyonları
        combinations = self.get_parameter_combinations()
        print(f"🔍 {len(combinations)} parametre kombinasyonu test edilecek\n")
        print("="*80)

        # Her window için
        all_results = {}

        for window in windows:
            print(f"\n🔄 {window['name']} - Q{window['train_quarters'][0]}-Q{window['train_quarters'][1]} TRAIN → Q{window['test_quarters'][0]}-Q{window['test_quarters'][1]} TEST")
            print("-"*80)

            # Train data üzerinde optimize et
            print(f"⏳ Train data üzerinde optimizasyon yapılıyor...")
            best_params, train_roi = self.optimize_on_train(window['train_data'], combinations)

            if best_params is None:
                print("❌ Uygun parametre bulunamadı!")
                continue

            min_str, tp, sl, trail_act, trail_dist = best_params

            print(f"✅ En iyi parametreler bulundu:")
            print(f"   min_strength: {min_str}")
            print(f"   TP: {tp*100:.1f}%, SL: {sl*100:.1f}%")
            print(f"   Trailing: {trail_act:.1f}% / {trail_dist:.1f}%")
            print(f"   Train ROI: {train_roi:+.2f}%")

            # Test data üzerinde test et
            print(f"\n⏳ Test data üzerinde test ediliyor...")
            test_result = self.test_on_forward(window['test_data'], best_params)

            print(f"✅ Test sonuçları:")
            print(f"   ROI: {test_result['roi']:+.2f}%")
            print(f"   Trades: {test_result['num_trades']}")
            print(f"   Win Rate: {test_result['win_rate']:.1f}%")

            # Kaydet
            param_key = f"{min_str}_{tp}_{sl}_{trail_act}_{trail_dist}"

            if param_key not in all_results:
                all_results[param_key] = {
                    'params': best_params,
                    'windows': [],
                    'train_rois': [],
                    'test_rois': []
                }

            all_results[param_key]['windows'].append(window['name'])
            all_results[param_key]['train_rois'].append(train_roi)
            all_results[param_key]['test_rois'].append(test_result['roi'])

        print("\n" + "="*80)
        print("GENEL SONUÇLAR")
        print("="*80)

        # En tutarlı parametreyi bul
        best_overall = None
        best_score = -float('inf')

        for param_key, data in all_results.items():
            if len(data['test_rois']) == 0:
                continue

            # Tutarlılık skoru: ortalama test ROI - standart sapma
            avg_test_roi = np.mean(data['test_rois'])
            std_test_roi = np.std(data['test_rois'])
            consistency_score = avg_test_roi - std_test_roi

            if consistency_score > best_score:
                best_score = consistency_score
                best_overall = (param_key, data)

        if best_overall:
            param_key, data = best_overall
            min_str, tp, sl, trail_act, trail_dist = data['params']

            print(f"\n🏆 EN İYİ PARAMETRE SETİ:")
            print("-"*80)
            print(f"   min_strength: {min_str}")
            print(f"   TP: {tp*100:.1f}%")
            print(f"   SL: {sl*100:.1f}%")
            print(f"   Trailing Activation: {trail_act:.1f}%")
            print(f"   Trailing Distance: {trail_dist:.1f}%")
            print(f"\n📊 PERFORMANS:")
            print(f"   Ortalama Test ROI: {np.mean(data['test_rois']):+.2f}%")
            print(f"   Test ROI Std Dev: {np.std(data['test_rois']):.2f}%")
            print(f"   Tutarlılık Skoru: {best_score:.2f}")
            print(f"\n📋 DETAYLAR:")

            for i, window_name in enumerate(data['windows']):
                print(f"   {window_name}: Train {data['train_rois'][i]:+.2f}% → Test {data['test_rois'][i]:+.2f}%")

        print("\n" + "="*80)


def main():
    print("\n" + "="*80)
    print("INTRADAY WALK-FORWARD OPTIMIZER")
    print("="*80)
    print("""
Bu script intraday strateji parametrelerini walk-forward
yöntemi ile optimize eder.

Yöntem:
  1. 2 yıllık veri → 8 çeyrek
  2. Her döngü: 2 çeyrek train → 2 çeyrek test
  3. 4 farklı window test edilir
  4. En tutarlı performansı veren parametreler seçilir

⚠️  Bu işlem uzun sürebilir (30-60 dakika)!
    """)

    confirm = input("Başlatmak istiyor musunuz? (y/n): ").lower()

    if confirm != 'y':
        print("İptal edildi.")
        return

    optimizer = IntradayWalkForwardOptimizer(initial_capital=10000)
    optimizer.run()


if __name__ == '__main__':
    main()
