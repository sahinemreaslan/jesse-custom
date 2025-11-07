"""
STRATEGY BATCH TESTER - Paralel Strateji Test Sistemi
═══════════════════════════════════════════════════════════
Tüm stratejileri paralel olarak test eder (multiprocessing)
En iyi performansı göstereni bulur
(GÜNCELLENDİ: Gelişmiş Intraday Ticaret Yönetimi Kullanıyor)
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
from multiprocessing import Pool, cpu_count
import time

from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from technical_indicators import TechnicalIndicators
from strategy_factory import StrategyFactory, Strategy
from intraday_strategy_config import INTRADAY_CONFIG


def load_data():
    """15 dakikalık verileri yükle"""
    print("⏳ Veritabanından veri yükleniyor...")

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
    return df


def prepare_data(df):
    """Veriyi hazırla - tüm indicator'ları ekle"""
    print("⏳ Teknik göstergeler hesaplanıyor...")

    # Fraktal analiz
    df = FractalAnalyzer.analyze_series(df)
    analyzer = MultiTimeframeFractalAnalyzer(weights=INTRADAY_CONFIG['weights'])
    df = analyzer.calculate_fractal_score(df)

    # Teknik göstergeler
    df = TechnicalIndicators.add_all_indicators(df)

    print(f"✅ Tüm göstergeler eklendi")
    return df


def backtest_strategy(args):
    """
    Bir stratejiyi backtest et (paralel çalıştırma için)
    GÜNCELLENDİ: INTRADAY_CONFIG'deki gelişmiş ticaret yönetimi kurallarını kullanır.
    """
    strategy, df_dict, initial_capital, commission = args

    # DataFrame'i yeniden oluştur (multiprocessing için)
    df = pd.DataFrame(df_dict)

    capital = initial_capital
    position = None
    trades = []

    # === INTRADAY_CONFIG'den Gelişmiş Kuralları Yükle ===
    config = INTRADAY_CONFIG.copy()
    tm_config = config['trade_management']
    
    # Ana TP/SL
    tp_percent = config['tp_percent']
    sl_percent = config['sl_percent']
    
    # Breakeven (Başabaş)
    use_breakeven = tm_config['use_breakeven']
    be_act_pct = tm_config['breakeven_activation']
    be_offset_factor = 1.0 + (tm_config['breakeven_offset'] / 100.0) # ör: 1.001
    
    # Trailing Stop (İz Süren Stop)
    use_trailing = tm_config['use_trailing_stop']
    trail_act_pct = tm_config['trailing_stop_activation']
    trail_dist_pct = tm_config['trailing_stop_distance']
    trail_dist_factor = 1.0 - (trail_dist_pct / 100.0) # ör: 0.995

    # (NOT: Partial exits (kısmi çıkışlar) bu basit backtester'ın
    # mantığına uymadığı için şimdilik uygulanmamıştır.
    # Breakeven ve Trailing kârlılığı test etmek için yeterlidir.)

    for idx in range(len(df)):
        row = df.iloc[idx]
        current_price = row['close']
        high = row['high']
        low = row['low']

        if position:
            # === GELİŞMİŞ POZİSYON YÖNETİMİ ===
            
            # 1. En yüksek fiyatı güncelle
            position['highest_price'] = max(position['highest_price'], high)
            profit_pct = ((position['highest_price'] - position['entry_price']) / position['entry_price']) * 100

            # 2. Başabaş (Breakeven) Kontrolü (sadece bir kez çalışır)
            if (use_breakeven and 
                not position['breakeven_active'] and 
                profit_pct >= be_act_pct):
                
                new_sl = position['entry_price'] * be_offset_factor
                if new_sl > position['sl']:
                    position['sl'] = new_sl
                    position['breakeven_active'] = True

            # 3. İz Süren Stop (Trailing) Aktivasyon Kontrolü (sadece bir kez çalışır)
            if (use_trailing and 
                not position['trailing_active'] and 
                profit_pct >= trail_act_pct):
                
                position['trailing_active'] = True

            # 4. İz Süren Stop Fiyatını Güncelle (sürekli çalışır)
            if position['trailing_active']:
                new_trailing_sl = position['highest_price'] * trail_dist_factor
                # Stop loss sadece yukarı hareket edebilir
                if new_trailing_sl > position['sl']:
                    position['sl'] = new_trailing_sl

            # 5. Çıkış Kontrolü
            exit_reason = None
            exit_price = None

            if high >= position['tp']:
                exit_reason = 'TP'
                exit_price = position['tp']
            elif low <= position['sl']:
                # DİKKAT: 'sl' artık dinamiktir (orijinal SL, breakeven veya trailing olabilir)
                exit_reason = 'SL' 
                exit_price = position['sl']

            if exit_reason:
                profit = (exit_price - position['entry_price']) * position['qty']

                # Komisyon
                commission_entry = position['entry_price'] * position['qty'] * commission
                commission_exit = exit_price * position['qty'] * commission
                net_profit = profit - commission_entry - commission_exit

                capital += net_profit

                trades.append({
                    'profit': net_profit,
                    'profit_pct': ((exit_price - position['entry_price']) / position['entry_price']) * 100
                })

                position = None

        else:
            # === GİRİŞ KONTROLÜ ===
            if strategy.check_entry(row):
                entry_price = row['close']
                qty = (capital * config['position_size']) / entry_price

                position = {
                    'entry_price': entry_price,
                    'qty': qty,
                    'tp': entry_price * (1 + tp_percent),
                    'sl': entry_price * (1 - sl_percent), # Dinamik SL'in başlangıç değeri
                    'highest_price': entry_price,
                    'trailing_active': False,
                    'breakeven_active': False # Yeni durum
                }

    # Açık pozisyon varsa kapat
    if position:
        exit_price = df.iloc[-1]['close']
        profit = (exit_price - position['entry_price']) * position['qty']
        commission_total = (position['entry_price'] + exit_price) * position['qty'] * commission
        net_profit = profit - commission_total
        capital += net_profit
        trades.append({'profit': net_profit, 'profit_pct': ((exit_price - position['entry_price']) / position['entry_price']) * 100})

    # Sonuçlar
    roi = ((capital / initial_capital) - 1) * 100
    num_trades = len(trades)
    win_rate = len([t for t in trades if t['profit'] > 0]) / num_trades * 100 if num_trades > 0 else 0

    return {
        'strategy_name': strategy.name,
        'roi': roi,
        'num_trades': num_trades,
        'win_rate': win_rate,
        'final_capital': capital
    }


def main():
    print("\n" + "="*80)
    print("STRATEGY BATCH TESTER - Paralel Strateji Test Sistemi")
    print(" (GÜNCELLENDİ: Gelişmiş Intraday Ticaret Yönetimi Kullanıyor)")
    print("="*80)

    # CPU sayısı
    num_cpus = cpu_count()
    print(f"\n💻 CPU Sayısı: {num_cpus}")
    print(f"   Paralel işlem yapılacak: {min(num_cpus - 1, 15)} strateji aynı anda\n")

    # Veri yükle
    df = load_data()
    df = prepare_data(df)

    # Stratejileri oluştur
    print("\n" + "="*80)
    factory = StrategyFactory()
    strategies = factory.generate_strategies()
    print("="*80)

    # Test parametreleri
    initial_capital = 10000
    commission = 0.0005  # %0.05

    # DataFrame'i dict'e çevir (multiprocessing için)
    df_dict = df.to_dict('list')

    # Argümanları hazırla
    args_list = [(strategy, df_dict, initial_capital, commission) for strategy in strategies]

    print("\n" + "="*80)
    print("🚀 TÜM STRATEJİLER TEST EDİLİYOR (PARALEL)")
    print("="*80)
    print(f"\n   Test edilecek strateji: {len(strategies)}")
    print(f"   Veri: {len(df)} mum (2 yıl)")
    print(f"   Sermaye: ${initial_capital:,.0f}")
    print(f"   Komisyon: %{commission*100}")
    print(f"   Ticaret Yönetimi: Gelişmiş (Trailing + Breakeven)")
    print("\n⏳ Test başladı...\n")

    start_time = time.time()

    # Paralel test
    with Pool(processes=min(num_cpus - 1, 15)) as pool:
        results = pool.map(backtest_strategy, args_list)

    elapsed = time.time() - start_time

    print(f"\n✅ Tüm stratejiler test edildi! ({elapsed:.1f} saniye)")

    # Sonuçları sırala
    results.sort(key=lambda x: x['roi'], reverse=True)

    # En iyi 10'u göster
    print("\n" + "="*80)
    print("📊 EN İYİ 10 STRATEJİ (Gelişmiş Yönetim ile)")
    print("="*80)
    print(f"\n{'#':<4} {'Strateji':<35} {'ROI':<12} {'Trades':<10} {'Win%':<8}")
    print("-"*80)

    for i, result in enumerate(results[:10], 1):
        print(f"{i:<4} {result['strategy_name']:<35} {result['roi']:+10.2f}% {result['num_trades']:<10} {result['win_rate']:>6.1f}%")

    # En kötü 5'i göster
    print("\n" + "="*80)
    print("⚠️  EN KÖTÜ 5 STRATEJİ (Gelişmiş Yönetim ile)")
    print("="*80)
    print(f"\n{'#':<4} {'Strateji':<35} {'ROI':<12} {'Trades':<10} {'Win%':<8}")
    print("-"*80)

    for i, result in enumerate(results[-5:], len(results)-4):
        print(f"{i:<4} {result['strategy_name']:<35} {result['roi']:+10.2f}% {result['num_trades']:<10} {result['win_rate']:>6.1f}%")

    # İstatistikler
    print("\n" + "="*80)
    print("📊 GENEL İSTATİSTİKLER")
    print("="*80)

    positive_roi = [r for r in results if r['roi'] > 0]
    negative_roi = [r for r in results if r['roi'] < 0]

    print(f"\n   Toplam Test Edilen: {len(results)}")
    print(f"   Karlı Stratejiler: {len(positive_roi)} ({len(positive_roi)/len(results)*100:.1f}%)")
    print(f"   Zararlı Stratejiler: {len(negative_roi)} ({len(negative_roi)/len(results)*100:.1f}%)")
    print(f"   Ortalama ROI: {np.mean([r['roi'] for r in results]):+.2f}%")
    print(f"   Medyan ROI: {np.median([r['roi'] for r in results]):+.2f}%")
    print(f"   En Yüksek ROI: {max(r['roi'] for r in results):+.2f}%")
    print(f"   En Düşük ROI: {min(r['roi'] for r in results):+.2f}%")

    print("\n" + "="*80)
    print(f"\n🏆 KAZANAN: {results[0]['strategy_name']}")
    print(f"   ROI: {results[0]['roi']:+.2f}%")
    print(f"   Trades: {results[0]['num_trades']}")
    print(f"   Win Rate: {results[0]['win_rate']:.1f}%")
    print("\n" + "="*80)


if __name__ == '__main__':
    main()