"""
ROBUSTNESS TESTER - Strateji Sağlamlık Testi
═══════════════════════════════════════════════════════════
Tek bir kârlı stratejiyi (Trailing Stop Master) alır ve
8 farklı zaman diliminde test ederek sağlamlığını ölçer.

Strateji her zaman diliminde kârlı mı?
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
import time

# Final stratejideki kârlı test motorunu ve analiz araçlarını içe aktar
from final_strategy import run_backtest, FINAL_STRATEGY
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer

# ═══════════════════════════════════════════════════════════
# ZAMAN DİLİMİNE ÖZEL PARAMETRELER
# ═══════════════════════════════════════════════════════════
# Her zaman diliminin "nefes alma" alanı farklıdır.
# 1h için %30 TP, 5m için imkansızdır.
# Bu yüzden, her zaman dilimi için mantıklı parametreler tanımlıyoruz.

TIMEFRAME_PARAMS = {
    # Not: DB'deki '1D' (günlük) 'D' veya '1d' olabilir,
    # 'timeframe' sütununuzu kontrol edin. '1D' varsayılmıştır.
    '1D': {
        'tp_percent': 0.60,   # %60 TP
        'sl_percent': 0.20,   # %20 SL
        'trade_management': {
            'trailing_stop_activation': 25.0, # %25 kârda
            'trailing_stop_distance': 10.0,   # %10 takip
            'breakeven_activation': 15.0,     # %15 kârda
            'breakeven_offset': 1.0,
        }
    },
    '4h': {
        'tp_percent': 0.40,   # %40 TP
        'sl_percent': 0.12,   # %12 SL
        'trade_management': {
            'trailing_stop_activation': 10.0, # %10 kârda
            'trailing_stop_distance': 5.0,    # %5 takip
            'breakeven_activation': 8.0,      # %8 kârda
            'breakeven_offset': 0.5,
        }
    },
    '1h': {
        'tp_percent': 0.30,   # %30 TP (Kanıtlanmış)
        'sl_percent': 0.08,   # %8 SL (Kanıtlanmış)
        'trade_management': {
            'trailing_stop_activation': 5.0,  # %5 kârda (Kanıtlanmış)
            'trailing_stop_distance': 3.5,    # %3.5 takip (Kanıtlanmış)
            'breakeven_activation': 3.0,      # %3 kârda
            'breakeven_offset': 0.5,
        }
    },
    '30m': {
        'tp_percent': 0.10,   # %10 TP
        'sl_percent': 0.03,   # %3 SL
        'trade_management': {
            'trailing_stop_activation': 3.0,
            'trailing_stop_distance': 1.5,
            'breakeven_activation': 2.0,
            'breakeven_offset': 0.2,
        }
    },
    '15m': {
        'tp_percent': 0.03,   # %3 TP (En son 'gevşek' testimiz)
        'sl_percent': 0.01,   # %1 SL
        'trade_management': {
            'trailing_stop_activation': 2.0,
            'trailing_stop_distance': 1.0,
            'breakeven_activation': 1.5,
            'breakeven_offset': 0.1,
        }
    },
    '5m': {
        'tp_percent': 0.015,  # %1.5 TP
        'sl_percent': 0.007,  # %0.7 SL
        'trade_management': {
            'trailing_stop_activation': 0.8,  # %0.8 kârda
            'trailing_stop_distance': 0.4,    # %0.4 takip
            'breakeven_activation': 0.5,      # %0.5 kârda
            'breakeven_offset': 0.1,
        }
    }
    # 8h ve 2h atlandı, 6 timeframe test için yeterlidir.
    # Gerekirse listeye eklenebilir.
}

# Test periyodu (Tüm zaman dilimleri için 2023-2024)
START_TS = 1672531200000  # 2023-01-01
END_TS = 1735689599000    # 2024-12-31 (Gelecek)


def load_data_robust(timeframe, start_ts, end_ts):
    """Veritabanından istenen zaman dilimini yükle"""
    print(f"  ⏳ Veri yükleniyor ({timeframe})...", end='', flush=True)
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

    query = f"""
        SELECT timestamp, open, high, low, close, volume
        FROM candle
        WHERE exchange = 'Binance Futures'
          AND symbol = 'BTC-USDT'
          AND timeframe = %s
          AND timestamp >= %s
          AND timestamp <= %s
        ORDER BY timestamp ASC;
    """
    
    try:
        df = pd.read_sql_query(query, conn, params=(timeframe, start_ts, end_ts))
        conn.close()
        print(f" {len(df)} mum yüklendi.")
        return df
    except Exception as e:
        conn.close()
        print(f" HATA: {e}")
        return pd.DataFrame()


def main():
    """Ana Sağlamlık Testi fonksiyonu"""
    print("="*80)
    print("STRATEJİ SAĞLAMLIK TESTİ (ROBUSTNESS TESTER)")
    print(f"Strateji: {FINAL_STRATEGY['name']}")
    print("="*80)
    print(f"\nTest Periyodu: 2023-01-01 - 2024-12-31")
    print(f"Test Edilen Zaman Dilimleri: {', '.join(TIMEFRAME_PARAMS.keys())}")
    print("\n" + "="*80)

    results = []
    start_time_total = time.time()

    for timeframe, params in TIMEFRAME_PARAMS.items():
        print(f"\n🧪 Test Başlıyor: Zaman Dilimi = {timeframe}")
        
        # 1. Veri Yükle
        df = load_data_robust(timeframe, START_TS, END_TS)
        if len(df) < 100:
            print(f"  ❌ Yetersiz veri. Test atlanıyor.")
            continue
            
        # 2. Strateji Konfigürasyonunu Hazırla
        # Ana stratejiyi al, üzerine zaman dilimi parametrelerini yaz
        config = FINAL_STRATEGY.copy()
        config.update(params)
        
        # trade_management'ı özel olarak güncelle
        config['trade_management'] = FINAL_STRATEGY['trade_management'].copy()
        config['trade_management'].update(params['trade_management'])

        # 3. Backtest'i Çalıştır
        print(f"  🚀 Backtest çalıştırılıyor...", end='', flush=True)
        start_test_time = time.time()
        
        result = run_backtest(df, config)
        
        elapsed_test = time.time() - start_test_time
        print(f" tamamlandı ({elapsed_test:.1f}s).")

        # 4. Sonuçları Kaydet
        if result:
            result['timeframe'] = timeframe
            results.append(result)
            print(f"  ✅ Sonuç: {result['roi']:+.2f}% ROI, {len(result['trades'])} işlem.")
        else:
            print(f"  ❌ Test başarısız oldu.")

    elapsed_total = time.time() - start_time_total
    print("\n" + "="*80)
    print(f"✅ TÜM SAĞLAMLIK TESTLERİ TAMAMLANDI ({elapsed_total:.1f} saniye)")
    print("="*80)
    print("\n📊 ÖZET RAPOR: Trailing Stop Master Stratejisi\n")

    if not results:
        print("Hiçbir sonuç üretilemedi.")
        return

    # En kârlıdan en az kârlıya sırala
    results.sort(key=lambda x: x['roi'], reverse=True)

    print(f"{'Zaman Dilimi':<15} {'ROI (%)':<12} {'İşlem Sayısı':<15} {'Kazanma %':<12} {'Max DD (%)':<15}")
    print("─" * 80)

    for r in results:
        num_trades = len(r['trades'])
        if num_trades > 0:
            winning = [t for t in r['trades'] if t['profit'] > 0]
            win_rate = (len(winning) / num_trades) * 100
        else:
            win_rate = 0.0

        print(f"{r['timeframe']:<15} "
              f"{r['roi']:>+10.2f}% "
              f"{num_trades:>14} "
              f"{win_rate:>10.1f}% "
              f"{r['max_drawdown']:>13.2f}%")

    print("\n" + "="*80)
    
    # Kârlı / Zararlı
    profitable = [r for r in results if r['roi'] > 0]
    unprofitable = [r for r in results if r['roi'] <= 0]
    
    print(f"\nDEĞERLENDİRME:")
    print(f"  Toplam Test: {len(results)}")
    print(f"  Kârlı Dilimler: {len(profitable)} ({', '.join(r['timeframe'] for r in profitable)})")
    print(f"  Zararlı Dilimler: {len(unprofitable)}")
    
    if len(profitable) > len(results) / 2:
        print("\n🎉 SONUÇ: Strateji SAĞLAM (Robust) görünüyor!")
    else:
        print("\n⚠️  SONUÇ: Strateji SAĞLAM DEĞİL. Performans zaman dilimine çok bağlı.")
        
    print("\n" + "="*80)


if __name__ == '__main__':
    # UserWarning'leri (SQLAlchemy) gizle
    import warnings
    warnings.filterwarnings('ignore', 'pandas only supports SQLAlchemy connectable')
    
    main()