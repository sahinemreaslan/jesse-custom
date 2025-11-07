"""
CANLI SİNYAL MONİTÖRÜ
═══════════════════════════════════════════════════════════
Amaç: Gerçek zamanlı olarak piyasayı izle ve
      Trailing Stop Master sinyalleri üret

Kullanım:
  python live_signal_monitor.py

Özellikler:
  - Canlı fraktal analiz
  - Giriş sinyali tespiti
  - Pozisyon yönetimi önerileri
  - Risk hesaplaması
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer


# FINAL STRATEJİ PARAMETRELERİ
STRATEGY_CONFIG = {
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
}


def get_latest_candles(hours=200):
    """Son X saatlik verileri çek"""
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

    # Son X saat
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)

    query = f'''
        SELECT timestamp, open, high, low, close, volume
        FROM candle
        WHERE exchange = 'Binance Futures'
          AND symbol = 'BTC-USDT'
          AND timeframe = '1h'
          AND timestamp >= {start_ts}
          AND timestamp <= {end_ts}
        ORDER BY timestamp DESC
        LIMIT {hours};
    '''

    df = pd.read_sql_query(query, conn)
    conn.close()

    # Ters çevir (eskiden yeniye)
    df = df.iloc[::-1].reset_index(drop=True)

    return df


def analyze_current_market():
    """Güncel piyasa durumunu analiz et"""

    print("="*80)
    print("CANLI SİNYAL MONİTÖRÜ - TRAILING STOP MASTER")
    print("="*80)
    print(f"\n📅 Analiz Zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n⏳ Veriler yükleniyor...")

    # Son 200 saatlik veri
    df = get_latest_candles(200)

    if len(df) < 50:
        print("❌ Yetersiz veri!")
        return

    print(f"✅ {len(df)} mum yüklendi (son {len(df)} saat)")

    # Fraktal analiz
    df = FractalAnalyzer.analyze_series(df)
    analyzer = MultiTimeframeFractalAnalyzer(weights=STRATEGY_CONFIG['weights'])
    df = analyzer.calculate_fractal_score(df)

    # Son mum
    latest = df.iloc[-1]
    current_price = latest['close']
    pattern = latest.get('fractal_pattern', 'Unknown')
    strength = latest.get('fractal_strength', 0)
    fractal_score = latest.get('fractal_score', 0)

    # MEVCUT DURUM
    print("\n" + "="*80)
    print("📊 GÜNCEL PİYASA DURUMU")
    print("="*80)

    print(f"\n💰 BTC-USDT Fiyat: ${current_price:,.2f}")
    print(f"📈 Fraktal Pattern: {pattern}")
    print(f"💪 Pattern Strength: {strength:.1f}")
    print(f"⭐ Fraktal Score: {fractal_score:.1f}")

    # Son 5 mumun analizi
    print("\n" + "="*80)
    print("📊 SON 5 MUM ANALİZİ")
    print("="*80)

    print(f"\n{'Zaman':<20} {'Fiyat':<12} {'Pattern':<15} {'Strength':<10} {'Score':<10}")
    print("─" * 80)

    for i in range(max(0, len(df)-5), len(df)):
        row = df.iloc[i]
        ts = datetime.fromtimestamp(row['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M')
        price = row['close']
        pat = row.get('fractal_pattern', 'N/A')
        str_val = row.get('fractal_strength', 0)
        score = row.get('fractal_score', 0)

        marker = "👉" if i == len(df)-1 else "  "
        print(f"{ts:<20} ${price:>9,.2f} {pat:<15} {str_val:>6.1f}    {score:>6.1f} {marker}")

    # SİNYAL ANALİZİ
    print("\n" + "="*80)
    print("🎯 SİNYAL ANALİZİ")
    print("="*80)

    # Giriş sinyali kontrolü
    entry_signal = False

    if pattern in STRATEGY_CONFIG['entry_patterns'] and strength >= STRATEGY_CONFIG['min_strength']:
        entry_signal = True

        print("\n🚀 GİRİŞ SİNYALİ TESPİT EDİLDİ!")
        print("─" * 80)
        print(f"   Pattern: {pattern} ✅")
        print(f"   Strength: {strength:.1f} (min: {STRATEGY_CONFIG['min_strength']}) ✅")
        print(f"   Fractal Score: {fractal_score:.1f}")

        # Pozisyon önerisi
        capital = 10000  # Örnek sermaye
        position_size_usd = capital * STRATEGY_CONFIG['position_size']
        quantity = position_size_usd / current_price

        entry_price = current_price
        tp_price = entry_price * (1 + STRATEGY_CONFIG['tp_percent'])
        sl_price = entry_price * (1 - STRATEGY_CONFIG['sl_percent'])

        risk_per_trade = position_size_usd * STRATEGY_CONFIG['sl_percent']
        reward_per_trade = position_size_usd * STRATEGY_CONFIG['tp_percent']
        risk_reward_ratio = reward_per_trade / risk_per_trade

        print(f"\n📋 POZİSYON ÖNERİSİ:")
        print(f"   Sermaye: ${capital:,.2f}")
        print(f"   Pozisyon Boyutu: %{STRATEGY_CONFIG['position_size']*100:.0f} (${position_size_usd:,.2f})")
        print(f"   Miktar: {quantity:.6f} BTC")

        print(f"\n💵 FİYAT SEVİYELERİ:")
        print(f"   Giriş: ${entry_price:,.2f}")
        print(f"   Take Profit: ${tp_price:,.2f} (+{STRATEGY_CONFIG['tp_percent']*100:.1f}%)")
        print(f"   Stop Loss: ${sl_price:,.2f} (-{STRATEGY_CONFIG['sl_percent']*100:.1f}%)")

        print(f"\n⚖️  RİSK YÖNETİMİ:")
        print(f"   Risk/Trade: ${risk_per_trade:,.2f} ({STRATEGY_CONFIG['sl_percent']*100:.1f}% of position)")
        print(f"   Reward/Trade: ${reward_per_trade:,.2f} ({STRATEGY_CONFIG['tp_percent']*100:.1f}% of position)")
        print(f"   Risk/Reward Ratio: 1:{risk_reward_ratio:.2f}")

        print(f"\n🛡️  TRAILING STOP:")
        print(f"   Aktivasyon: ${entry_price * (1 + STRATEGY_CONFIG['trailing_stop_activation']):,.2f} (+{STRATEGY_CONFIG['trailing_stop_activation']*100:.1f}%)")
        print(f"   Distance: {STRATEGY_CONFIG['trailing_stop_distance']*100:.1f}%")

    else:
        print("\n⏸️  GİRİŞ SİNYALİ YOK")
        print("─" * 80)

        reasons = []

        if pattern not in STRATEGY_CONFIG['entry_patterns']:
            reasons.append(f"❌ Pattern uygun değil: {pattern} (Beklenen: {', '.join(STRATEGY_CONFIG['entry_patterns'])})")
        else:
            reasons.append(f"✅ Pattern uygun: {pattern}")

        if strength < STRATEGY_CONFIG['min_strength']:
            reasons.append(f"❌ Strength yetersiz: {strength:.1f} (Min: {STRATEGY_CONFIG['min_strength']})")
        else:
            reasons.append(f"✅ Strength yeterli: {strength:.1f}")

        for reason in reasons:
            print(f"   {reason}")

        print("\n💡 BEKLEME MODUNDAYıZ - Sinyal için piyasayı izlemeye devam et")

    # TREND ANALİZİ
    print("\n" + "="*80)
    print("📈 TREND ANALİZİ (Son 24 saat)")
    print("="*80)

    recent_24h = df.tail(24)

    if len(recent_24h) >= 24:
        patterns_24h = recent_24h['fractal_pattern'].value_counts()

        print("\nPattern Dağılımı:")
        for pat, count in patterns_24h.items():
            pct = (count / 24) * 100
            bar = "█" * int(pct / 5)
            print(f"   {pat:15} → {count:2} mum ({pct:5.1f}%) {bar}")

        # Dominant trend
        dominant = patterns_24h.index[0] if len(patterns_24h) > 0 else "Unknown"
        print(f"\n🎯 Dominant Pattern: {dominant}")

        if dominant in ['Trending Up', 'Outside Bar']:
            print("   💹 YUKARI TREND - Potansiyel giriş fırsatları olabilir")
        elif dominant == 'Trending Down':
            print("   📉 AŞAĞI TREND - Dikkatli ol, giriş yapma!")
        else:
            print("   ↔️  YATAY PIYASA - Konsolidasyon")

    print("\n" + "="*80)
    print("✅ Analiz tamamlandı!")
    print("="*80)

    if entry_signal:
        print("\n🚀 AKSİYON GEREKLİ: Yukarıdaki pozisyon önerisini değerlendir!")
    else:
        print("\n⏸️  AKSİYON: Bekle ve piyasayı izlemeye devam et")

    print("\n💡 İpucu: Bu scripti her saat çalıştırarak yeni sinyalleri takip et")
    print("         Crontab ile otomatik yapabilirsin!")


def main():
    """Ana fonksiyon"""
    try:
        analyze_current_market()
    except Exception as e:
        print(f"\n❌ HATA: {str(e)}")
        print("\nLütfen:")
        print("  1. PostgreSQL çalışıyor mu kontrol et")
        print("  2. Veritabanında güncel veri var mı kontrol et")
        print("  3. import_data.py ile yeni veri çek")


if __name__ == '__main__':
    main()
