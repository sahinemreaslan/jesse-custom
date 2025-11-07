"""
ADIM 4: WALK-FORWARD TESTİ
═══════════════════════════════════════════════════════════
Amaç: Stratejinin farklı piyasa koşullarında tutarlılığını test et
      - 2023-2024 verisini 3 aylık dilimlere böl
      - Her dilimde stratejiyi test et
      - Tutarlılık skorunu hesapla
      - Over-fitting kontrolü yap

Neden: Strateji geçmiş bir dönemde iyi çalışabilir ama
       gelecekte aynı performansı gösteremeyebilir.
       Walk-forward test over-fitting'i tespit eder.
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from advanced_trade_manager import TradeManager


def load_data_range(start_ts, end_ts):
    """Belirli timestamp aralığı için veri yükle"""
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

    query = f'''
        SELECT timestamp, open, high, low, close, volume
        FROM candle
        WHERE exchange = 'Binance Futures'
          AND symbol = 'BTC-USDT'
          AND timeframe = '1h'
          AND timestamp >= {start_ts}
          AND timestamp <= {end_ts}
        ORDER BY timestamp ASC;
    '''

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def run_backtest_period(df):
    """Partial Exit Pro stratejisini çalıştır"""
    config = {
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'min_strength': 30,
        'position_size': 0.20,
        'tp_percent': 0.30,
        'sl_percent': 0.10,
        'weights': {
            'TRENDING_UP': 2.5,
            'OUTSIDE_BAR': 3.0,
            'TRENDING_DOWN': 2.0,
            'INSIDE_BAR': 0.5
        },
        'trade_management': {
            'use_partial_exit': True,
            'partial_exit_levels': [
                {'price_pct': 8.0, 'qty_pct': 0.33},
                {'price_pct': 15.0, 'qty_pct': 0.33},
            ],
            'use_trailing_stop': True,
            'trailing_stop_activation': 10.0,
            'trailing_stop_distance': 4.0,
            'use_breakeven': True,
            'breakeven_activation': 5.0,
            'breakeven_offset': 1.0,
            'use_momentum_exit': False,
            'use_time_exit': False
        }
    }

    if len(df) < 100:
        return None

    # Fraktal analiz
    df = FractalAnalyzer.analyze_series(df)
    analyzer = MultiTimeframeFractalAnalyzer(weights=config['weights'])
    df = analyzer.calculate_fractal_score(df)

    # Trade manager
    trade_manager = TradeManager(config['trade_management'])

    # Backtest
    balance = 10000
    position = None
    trades = []

    for i in range(50, len(df)):
        row = df.iloc[i]
        price = row['close']
        pattern = row.get('fractal_pattern')
        strength = row.get('fractal_strength', 0)
        fractal_score = row.get('fractal_score', 0)

        # Pozisyon güncelleme
        if position is not None:
            update_result = trade_manager.update_position(
                position, price, i, fractal_score
            )

            if update_result['action'] in ['exit_full', 'exit_partial']:
                qty = update_result['exit_qty']
                profit = (price - position['entry_price']) * qty
                balance += profit

                if update_result['action'] == 'exit_full':
                    trades.append({
                        'profit': profit,
                        'balance_after': balance,
                        'exit_reason': update_result['exit_reason']
                    })
                    position = None
                else:
                    position = update_result['updated_position']
            else:
                position = update_result['updated_position']

        # Yeni giriş
        if position is None and pattern in config['entry_patterns'] and strength >= config['min_strength']:
            qty = (balance * config['position_size']) / price
            position = {
                'entry_price': price,
                'qty': qty,
                'remaining_qty': qty,
                'entry_index': i,
                'entry_fractal_score': fractal_score,
                'tp': price * (1 + config['tp_percent']),
                'sl': price * (1 - config['sl_percent']),
                'stop_loss': price * (1 - config['sl_percent']),
                'trailing_stop': 0,
                'partial_exits': []
            }

    return {
        'balance': balance,
        'trades': trades,
        'profit': balance - 10000,
        'roi': ((balance - 10000) / 10000) * 100
    }


def main():
    """Ana walk-forward test fonksiyonu"""
    print("="*80)
    print("ADIM 4: WALK-FORWARD TESTİ")
    print("="*80)
    print("\nStrateji: Partial Exit Pro")
    print("Periyot: 2023-2024 (3'er aylık dilimler)")
    print("\n" + "="*80)

    # 3 aylık periyotlar (yaklaşık)
    # 3 ay = ~90 gün = ~2160 saat = 2160 * 3600 * 1000 ms
    three_months_ms = 90 * 24 * 3600 * 1000

    # 2023-01-01 başlangıcı
    start_2023 = 1672531200000  # 2023-01-01
    end_2024 = 1704067199000     # 2024-12-31

    # Periyotları oluştur
    periods = []
    current_start = start_2023

    quarter_num = 1
    while current_start < end_2024:
        current_end = min(current_start + three_months_ms, end_2024)

        start_date = datetime.fromtimestamp(current_start / 1000).strftime('%Y-%m-%d')
        end_date = datetime.fromtimestamp(current_end / 1000).strftime('%Y-%m-%d')

        periods.append({
            'name': f'Q{quarter_num} ({start_date})',
            'start_ts': current_start,
            'end_ts': current_end
        })

        current_start = current_end + 1
        quarter_num += 1

    print(f"\n📅 {len(periods)} periyot test edilecek:\n")
    for p in periods:
        print(f"   • {p['name']}")

    print("\n" + "="*80)
    print("⏳ Walk-forward test başlıyor...\n")

    # Her periyodu test et
    results = []

    for i, period in enumerate(periods, 1):
        print(f"   [{i}/{len(periods)}] {period['name']}...", end='')

        # Veri yükle
        df = load_data_range(period['start_ts'], period['end_ts'])

        if len(df) < 100:
            print(f" ⚠️  Yetersiz veri ({len(df)} mum)")
            continue

        # Backtest çalıştır
        result = run_backtest_period(df)

        if result is None:
            print(" ⚠️  Test başarısız")
            continue

        result['period'] = period['name']
        result['num_candles'] = len(df)
        results.append(result)

        print(f" ✓ ({len(result['trades'])} işlem, {result['roi']:+.2f}%)")

    # SONUÇLAR
    print("\n" + "="*80)
    print("WALK-FORWARD SONUÇLARI")
    print("="*80)

    if len(results) == 0:
        print("\n❌ Hiç sonuç elde edilemedi!")
        return

    print(f"\n{'Periyot':<25} {'Getiri':<12} {'İşlem':<10} {'Kazanma':<10}")
    print("─" * 80)

    for result in results:
        trades = result['trades']
        num_trades = len(trades)

        if num_trades > 0:
            winning = [t for t in trades if t['profit'] > 0]
            win_rate = (len(winning) / num_trades) * 100
        else:
            win_rate = 0

        print(f"{result['period']:<25} {result['roi']:>6.2f}%{'':<5} {num_trades:<10} {win_rate:>5.1f}%")

    # TUTARLıLıK ANALİZİ
    print("\n" + "="*80)
    print("📊 TUTARLILIK ANALİZİ")
    print("="*80)

    rois = [r['roi'] for r in results]

    positive_periods = [r for r in results if r['roi'] > 0]
    negative_periods = [r for r in results if r['roi'] < 0]

    consistency_rate = (len(positive_periods) / len(results)) * 100

    print(f"\n🎯 GENEL İSTATİSTİKLER:")
    print(f"   Toplam Periyot: {len(results)}")
    print(f"   Karlı Periyot: {len(positive_periods)} ({consistency_rate:.1f}%)")
    print(f"   Zararlı Periyot: {len(negative_periods)} ({100-consistency_rate:.1f}%)")

    print(f"\n📈 GETİRİ DAĞILIMI:")
    print(f"   Ortalama ROI: {np.mean(rois):+.2f}%")
    print(f"   Medyan ROI: {np.median(rois):+.2f}%")
    print(f"   Standart Sapma: {np.std(rois):.2f}%")
    print(f"   En İyi: {max(rois):+.2f}%")
    print(f"   En Kötü: {min(rois):+.2f}%")

    # Tutarlılık Skoru
    print(f"\n⚖️  TUTARLILIK SKORU:")

    # 1. Pozitif periyot oranı
    consistency_score = consistency_rate

    # 2. Standart sapma (düşük = iyi)
    std_penalty = min(np.std(rois) / 10, 30)  # Max 30 puan ceza

    # 3. Medyan pozitif mi?
    median_bonus = 10 if np.median(rois) > 0 else 0

    final_score = consistency_score - std_penalty + median_bonus
    final_score = max(0, min(100, final_score))  # 0-100 arası

    print(f"   Pozitif Oran: +{consistency_rate:.1f} puan")
    print(f"   Volatilite Cezası: -{std_penalty:.1f} puan")
    print(f"   Medyan Bonusu: +{median_bonus:.1f} puan")
    print(f"   ───────────────────────")
    print(f"   TOPLAM: {final_score:.1f}/100")

    # DEĞERLENDİRME
    print("\n" + "="*80)
    print("📋 WALK-FORWARD DEĞERLENDİRMESİ")
    print("="*80)

    if final_score >= 80:
        print("\n✅ MÜKEMMEL: Strateji farklı piyasa koşullarında son derece tutarlı!")
        print("   → Over-fitting riski çok düşük")
        print("   → Gerçek trade için güvenilir")
    elif final_score >= 60:
        print("\n⚠️  İYİ: Strateji genel olarak tutarlı ama bazı periyotlarda zayıf")
        print("   → Orta seviye over-fitting riski")
        print("   → Dikkatli kullanılabilir")
    elif final_score >= 40:
        print("\n⚠️  ORTA: Strateji tutarsız sonuçlar veriyor")
        print("   → Yüksek over-fitting riski")
        print("   → Daha fazla test gerekli")
    else:
        print("\n❌ ZAYIF: Strateji farklı dönemlerde çok değişken!")
        print("   → Ciddi over-fitting problemi")
        print("   → Gerçek trade için riskli")

    # COMPOUND ETKİSİ
    print("\n" + "="*80)
    print("💰 COMPOUND ETKİSİ (Tüm Periyotlar Birleştirildi)")
    print("="*80)

    compound_balance = 10000
    for result in results:
        # Her periyot önceki balance üzerinden çalışıyor
        period_profit = (result['roi'] / 100) * compound_balance
        compound_balance += period_profit

    total_roi = ((compound_balance - 10000) / 10000) * 100

    print(f"\n   Başlangıç: $10,000")
    print(f"   Bitiş: ${compound_balance:,.2f}")
    print(f"   Toplam ROI: {total_roi:+.2f}%")

    print("\n" + "="*80)
    print("✅ Adım 4 tamamlandı!")
    print("="*80)

    # ÖNERİLER
    print("\n" + "="*80)
    print("💡 SONRAKİ ADIMLAR")
    print("="*80)
    print("""
Tüm optimizasyon adımları tamamlandı!

✅ Adım 1: Multi-year test → Strateji 2023 ve 2024'te tutarlı
✅ Adım 2: Position size → Optimal %20 pozisyon boyutu
✅ Adım 3: Risk/Reward → Risk metrikleri analiz edildi
✅ Adım 4: Walk-forward → Over-fitting kontrolü yapıldı

📌 SONRAKİ AŞAMA:
   → Gerçek piyasada paper trading ile test
   → İlk küçük pozisyonlarla canlı test
   → Sürekli monitoring ve ince ayar
    """)


if __name__ == '__main__':
    main()
