"""
MULTI-TIMEFRAME SCALPING STRATEGY PIPELINE - PART 2
═══════════════════════════════════════════════════════════
Walk-Forward Validation, Backtest Engine, Pipeline Orchestrator
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from multi_tf_strategy_pipeline import (
    MultiTimeframeDataLoader,
    MultiTFIndicatorCalculator,
    StrategyGenerator,
    RuleEvaluator
)


# ═══════════════════════════════════════════════════════════
# 5. BACKTEST ENGINE - Komisyonlu Backtest
# ═══════════════════════════════════════════════════════════

class ScalpingBacktestEngine:
    """Scalping stratejileri için backtest motoru"""

    def __init__(self, initial_capital=10000, commission=0.0004, leverage=1):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission = commission
        self.leverage = leverage
        self.position = None
        self.trades = []
        self.balance_history = [initial_capital]

    def calculate_commission(self, price, quantity):
        """Komisyon hesapla"""
        trade_value = price * quantity * self.leverage
        return trade_value * self.commission

    def open_position(self, row, strategy):
        """Pozisyon aç"""
        if self.position is not None:
            return

        entry_price = row['close']
        position_size = self.capital * 0.10  # %10 sermaye
        quantity = position_size / entry_price

        # Komisyon
        commission = self.calculate_commission(entry_price, quantity)
        self.capital -= commission

        self.position = {
            'entry_price': entry_price,
            'entry_time': row.name,
            'quantity': quantity,
            'strategy': strategy['name'],
            'tp': entry_price * (1 + strategy['tp_pct']),
            'sl': entry_price * (1 - strategy['sl_pct']),
            'entry_commission': commission,
        }

    def update_position(self, row):
        """Pozisyon güncelle"""
        if self.position is None:
            return None

        current_price = row['close']
        high = row['high']
        low = row['low']

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

        # PNL hesapla (kaldıraçlı)
        price_change = exit_price - self.position['entry_price']
        leveraged_pnl = price_change * self.position['quantity'] * self.leverage

        # Net PNL
        net_pnl = leveraged_pnl - self.position['entry_commission'] - exit_commission

        self.capital += net_pnl

        # Trade kaydı
        duration = (exit_time - self.position['entry_time']).total_seconds() / 60  # Dakika

        self.trades.append({
            'entry_time': self.position['entry_time'],
            'exit_time': exit_time,
            'entry_price': self.position['entry_price'],
            'exit_price': exit_price,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason,
            'strategy': self.position['strategy'],
            'duration_min': duration,
        })

        self.balance_history.append(self.capital)
        self.position = None

    def run_backtest(self, df, strategy):
        """Backtest çalıştır"""
        self.capital = self.initial_capital
        self.position = None
        self.trades = []
        self.balance_history = [self.initial_capital]

        for idx in range(len(df)):
            row = df.iloc[idx]

            if self.position:
                exit_info = self.update_position(row)
                if exit_info:
                    self.close_position(exit_info)
            else:
                # Giriş sinyali kontrol
                if RuleEvaluator.evaluate_strategy(row, strategy):
                    self.open_position(row, strategy)

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
            'trades': self.trades,
        }


# ═══════════════════════════════════════════════════════════
# 6. WALK-FORWARD VALIDATOR
# ═══════════════════════════════════════════════════════════

class WalkForwardValidator:
    """
    Walk-Forward Optimizasyon

    METODOLOJI:
    1. Veriyi çeyreklere böl (3 aylık periyotlar)
    2. Her iterasyonda:
       - 2 çeyrek TRAIN (optimizasyon)
       - 1 çeyrek TEST (doğrulama)
    3. Rolling window ile ilerle
    4. Overfitting tespiti için train vs test performansını karşılaştır
    """

    @staticmethod
    def split_into_quarters(df):
        """Veriyi çeyreklere böl"""
        total_days = (df.index[-1] - df.index[0]).days
        quarter_days = total_days // 8  # 8 çeyrek

        quarters = []
        start_date = df.index[0]

        for i in range(8):
            end_date = start_date + timedelta(days=quarter_days)
            quarter_df = df[(df.index >= start_date) & (df.index < end_date)]

            if len(quarter_df) > 0:
                quarters.append({
                    'num': i + 1,
                    'start': start_date,
                    'end': end_date,
                    'data': quarter_df
                })

            start_date = end_date

        return quarters

    @staticmethod
    def create_wf_windows(quarters):
        """Walk-forward windows oluştur"""
        windows = []

        for i in range(len(quarters) - 2):
            train_quarters = [quarters[i], quarters[i+1]]
            test_quarter = quarters[i+2]

            train_df = pd.concat([q['data'] for q in train_quarters])

            windows.append({
                'name': f"WF-{i+1}",
                'train_quarters': [q['num'] for q in train_quarters],
                'test_quarter': test_quarter['num'],
                'train_data': train_df,
                'test_data': test_quarter['data']
            })

        return windows

    @staticmethod
    def validate_strategy(strategy, df):
        """Bir stratejiyi walk-forward ile validate et"""
        quarters = WalkForwardValidator.split_into_quarters(df)

        if len(quarters) < 3:
            return None

        windows = WalkForwardValidator.create_wf_windows(quarters)

        wf_results = []

        for window in windows:
            # Train data üzerinde backtest
            engine_train = ScalpingBacktestEngine()
            train_result = engine_train.run_backtest(window['train_data'], strategy)

            # Test data üzerinde backtest
            engine_test = ScalpingBacktestEngine()
            test_result = engine_test.run_backtest(window['test_data'], strategy)

            if train_result and test_result:
                wf_results.append({
                    'window': window['name'],
                    'train_roi': train_result['roi'],
                    'test_roi': test_result['roi'],
                    'train_trades': train_result['num_trades'],
                    'test_trades': test_result['num_trades'],
                    'train_wr': train_result['win_rate'],
                    'test_wr': test_result['win_rate'],
                })

        if len(wf_results) == 0:
            return None

        # Overfitting metriği hesapla
        train_rois = [r['train_roi'] for r in wf_results]
        test_rois = [r['test_roi'] for r in wf_results]

        avg_train_roi = np.mean(train_rois)
        avg_test_roi = np.mean(test_rois)

        # Overfitting score: train ile test arasındaki fark
        overfitting_score = abs(avg_train_roi - avg_test_roi)

        # Consistency score: test ROI'nin standart sapması
        consistency_score = np.std(test_rois)

        return {
            'avg_train_roi': avg_train_roi,
            'avg_test_roi': avg_test_roi,
            'overfitting_score': overfitting_score,
            'consistency_score': consistency_score,
            'wf_windows': wf_results,
            'is_overfitted': overfitting_score > 10,  # %10'dan fazla fark = overfitting
            'is_consistent': consistency_score < 15,  # std < 15 = tutarlı
        }


# ═══════════════════════════════════════════════════════════
# 7. STRATEGY PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════

class StrategyPipeline:
    """Ana pipeline orchestrator"""

    def __init__(self, start_date='2024-01-01', end_date='2024-12-31'):
        self.start_date = start_date
        self.end_date = end_date
        self.df = None
        self.strategies = []
        self.results = []

    def run(self):
        """Pipeline'ı çalıştır"""
        print("\n" + "="*100)
        print("🚀 MULTI-TIMEFRAME SCALPING STRATEGY PIPELINE")
        print("="*100)

        # ADIM 1: Veri yükle
        print("\n📊 ADIM 1: Multi-Timeframe Veri Yükleme")
        print("-"*100)

        loader = MultiTimeframeDataLoader()
        self.df = loader.load_multi_timeframe(
            base_timeframe='15m',
            start_date=self.start_date,
            end_date=self.end_date
        )

        if self.df is None or len(self.df) == 0:
            print("❌ Veri yüklenemedi!")
            return

        # ADIM 2: İndikatörler hesapla
        print("\n🔧 ADIM 2: İndikatör Hesaplama")
        print("-"*100)

        self.df = MultiTFIndicatorCalculator.calculate_multi_tf_indicators(self.df)

        # NaN'ları temizle
        self.df = self.df.dropna()
        print(f"✅ Temizlendi: {len(self.df)} mum kaldı\n")

        # ADIM 3: Strateji kombinasyonları oluştur
        print("\n🎲 ADIM 3: Strateji Kombinasyonları")
        print("-"*100)

        self.strategies = StrategyGenerator.generate_rule_combinations()
        print()

        # ADIM 4: Her stratejiyi test et (basit backtest)
        print("\n🧪 ADIM 4: Hızlı Backtest (Tüm Stratejiler)")
        print("-"*100)

        for i, strategy in enumerate(self.strategies, 1):
            print(f"   {i}/{len(self.strategies)}: {strategy['name']}", end='')

            engine = ScalpingBacktestEngine()
            result = engine.run_backtest(self.df, strategy)

            if result:
                result['strategy_name'] = strategy['name']
                result['strategy_config'] = strategy
                self.results.append(result)
                print(f" → ROI: {result['roi']:+.2f}%, Trades: {result['num_trades']}, WR: {result['win_rate']:.1f}%")
            else:
                print(" → ❌ Hiç trade yok")

        # ADIM 5: En iyi stratejileri seç (top 3)
        print("\n" + "="*100)
        print("🏆 ADIM 5: En İyi Stratejileri Seçme")
        print("="*100)

        # ROI'ye göre sırala
        self.results.sort(key=lambda x: x['roi'], reverse=True)

        # Pozitif ROI olanları filtrele
        positive_results = [r for r in self.results if r['roi'] > 0]

        if len(positive_results) == 0:
            print("\n❌ Pozitif ROI veren strateji bulunamadı!")
            print("   → Parametreleri ayarlayın veya farklı kombinasyonlar deneyin")
            return

        print(f"\n✅ {len(positive_results)} pozitif ROI veren strateji bulundu\n")

        # Top 3'ü göster
        top_3 = positive_results[:3]

        for i, result in enumerate(top_3, 1):
            print(f"\n{'='*100}")
            print(f"#{i}: {result['strategy_name']}")
            print(f"{'='*100}")
            print(f"   ROI: {result['roi']:+.2f}%")
            print(f"   Trades: {result['num_trades']}")
            print(f"   Win Rate: {result['win_rate']:.1f}%")
            print(f"   Profit Factor: {result['profit_factor']:.2f}")
            print(f"   Max DD: {result['max_drawdown']:.2f}%")

        # ADIM 6: Top 3'ü walk-forward ile validate et
        print("\n" + "="*100)
        print("🔬 ADIM 6: Walk-Forward Validation (Top 3)")
        print("="*100)

        validated_results = []

        for i, result in enumerate(top_3, 1):
            strategy = result['strategy_config']
            print(f"\n{i}. {strategy['name']}")
            print("-"*100)

            wf_result = WalkForwardValidator.validate_strategy(strategy, self.df)

            if wf_result:
                print(f"   Train ROI (avg): {wf_result['avg_train_roi']:+.2f}%")
                print(f"   Test ROI (avg): {wf_result['avg_test_roi']:+.2f}%")
                print(f"   Overfitting Score: {wf_result['overfitting_score']:.2f}%")
                print(f"   Consistency (std): {wf_result['consistency_score']:.2f}%")

                if wf_result['is_overfitted']:
                    print(f"   ⚠️  OVERFITTED! (Train-Test farkı > %10)")
                else:
                    print(f"   ✅ Not overfitted")

                if wf_result['is_consistent']:
                    print(f"   ✅ Consistent (std < 15%)")
                else:
                    print(f"   ⚠️  İnconsistent (std > 15%)")

                result['wf_validation'] = wf_result
                validated_results.append(result)

        # ADIM 7: Final karar
        print("\n" + "="*100)
        print("✅ ADIM 7: FINAL KARAR")
        print("="*100)

        # Overfitting olmayan ve consistent olanları filtrele
        final_candidates = [
            r for r in validated_results
            if not r['wf_validation']['is_overfitted'] and r['wf_validation']['is_consistent']
        ]

        if len(final_candidates) == 0:
            print("\n⚠️  Overfitting olmayan strateji bulunamadı!")
            print("   En iyi 3'ü yine de göster:")
            final_candidates = validated_results[:3]

        # En yüksek test ROI'ye göre sırala
        final_candidates.sort(key=lambda x: x['wf_validation']['avg_test_roi'], reverse=True)

        print(f"\n🏆 EN İYİ STRATEJİ: {final_candidates[0]['strategy_name']}")
        print("="*100)

        best = final_candidates[0]
        print(f"""
Backtest Performansı:
  ROI: {best['roi']:+.2f}%
  Trades: {best['num_trades']}
  Win Rate: {best['win_rate']:.1f}%
  Profit Factor: {best['profit_factor']:.2f}
  Max Drawdown: {best['max_drawdown']:.2f}%

Walk-Forward Validasyon:
  Avg Test ROI: {best['wf_validation']['avg_test_roi']:+.2f}%
  Overfitting Score: {best['wf_validation']['overfitting_score']:.2f}%
  Consistency: {best['wf_validation']['consistency_score']:.2f}%

Strateji Kuralları:
        """)

        for rule in best['strategy_config']['rules']:
            print(f"  - {rule}")

        print(f"\nTP: {best['strategy_config']['tp_pct']*100}%")
        print(f"SL: {best['strategy_config']['sl_pct']*100}%")

        print("\n" + "="*100)
        print("✅ PİPELİNE TAMAMLANDI!")
        print("="*100)

        print("\n📋 Sonraki Adımlar:")
        print("  1. Paper trading ile 1 ay test et")
        print("  2. Küçük sermaye ile canlı test ($100-500)")
        print("  3. Performansı günlük takip et")
        print("  4. Başarılıysa kademeli artır")

        return final_candidates[0]


# ═══════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════

def main():
    """Pipeline'ı çalıştır"""

    # Tarih aralığı (direkt kullan)
    start_date = '2024-01-01'
    end_date = '2024-10-31'

    print(f"\n📅 Test Periyodu: {start_date} → {end_date}")

    # Pipeline oluştur ve çalıştır
    pipeline = StrategyPipeline(start_date=start_date, end_date=end_date)
    best_strategy = pipeline.run()

    return best_strategy


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')

    main()
