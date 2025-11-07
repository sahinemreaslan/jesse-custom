"""
INTRADAY OPTIMIZED CONFIG - İyileştirilmiş Gün İçi Strateji
═══════════════════════════════════════════════════════════
Sorunlar düzeltildi:
  ✅ Doğru parametre ölçekleme (volatilite bazlı)
  ✅ Komisyon dahil edildi
  ✅ Partial exit mantığı düzeltildi
  ✅ Risk/Reward optimize edildi

YAPILAN DEĞİŞİKLİKLER:
═══════════════════════════════════════════════════════════
1. PARAMETRE ÖLÇEKLENDİRME (Volatilite Bazlı):
   - 15m BTC volatilitesi: 1h'nin ~3x daha düşük
   - TP: %30 → %1.5 (20x değil, 3x ölçek + komisyon marjı)
   - SL: %8 → %0.6 (komisyon sonrası hala pozitif kalacak şekilde)

2. KOMİSYON ETKİSİ:
   - Binance Futures: %0.02 maker + %0.05 taker = ~%0.04 ortalama
   - Her trade: ~%0.08 total komisyon (giriş+çıkış)
   - Bu nedenle minimum TP > %0.1 olmalı

3. PARTIAL EXIT:
   - Kaldırıldı (intraday'de komisyon çok arttırıyor)
   - Trailing stop daha efektif

4. TRAILING STOP:
   - Aktivasyon: %0.8 (daha erken başlasın)
   - Distance: %0.3 (daha sıkı takip)

5. MIN STRENGTH:
   - 30 → 40 (daha kaliteli sinyaller için)
   - Daha az trade ama daha yüksek kalite

═══════════════════════════════════════════════════════════
"""

# OPTIMIZED INTRADAY CONFIG
INTRADAY_OPTIMIZED_CONFIG = {
    'name': 'Intraday Trailing Stop Master (Optimized)',
    'timeframe': '15m',

    # GİRİŞ KURALLARI
    'entry_patterns': ['Trending Up', 'Outside Bar'],
    'min_strength': 40,  # ↑ Daha yüksek kalite (30'dan 40'a)

    # POZİSYON BOYUTU
    'position_size': 0.10,  # ↓ Daha düşük risk (%15'ten %10'a)

    # TP/SL (Volatilite bazlı ölçekleme)
    'tp_percent': 0.015,  # %1.5 (komisyon sonrası ~%1.4 net)
    'sl_percent': 0.006,  # %0.6 (komisyon sonrası ~%0.5 net zarar)

    # FRAKTAL AĞIRLIKLARI (aynı)
    'weights': {
        'TRENDING_UP': 3.0,
        'OUTSIDE_BAR': 3.5,
        'TRENDING_DOWN': 2.0,
        'INSIDE_BAR': 0.3
    },

    # TRADE MANAGEMENT
    'trade_management': {
        # Trailing Stop (ana kar koruma aracı)
        'use_trailing_stop': True,
        'trailing_stop_activation': 0.8,   # %0.8 kârda aktif
        'trailing_stop_distance': 0.3,     # %0.3 mesafe

        # Breakeven (risksiz bölgeye geçiş)
        'use_breakeven': True,
        'breakeven_activation': 0.5,       # %0.5 kârda aktif
        'breakeven_offset': 0.05,          # +%0.05 kar garantisi

        # Partial Exit (KAPALI - komisyon maliyeti yüksek)
        'use_partial_exit': False,

        # Diğerleri
        'use_momentum_exit': False,
        'use_time_exit': False,
    },

    # KOMİSYON
    'commission': 0.0004,  # %0.04 (Binance Futures ortalama)
}


# ALTERNATİF 1: Daha Agresif (Daha fazla trade)
INTRADAY_AGGRESSIVE_CONFIG = {
    'name': 'Intraday Aggressive (More Trades)',
    'timeframe': '15m',
    'entry_patterns': ['Trending Up', 'Outside Bar'],
    'min_strength': 30,  # Daha düşük threshold
    'position_size': 0.08,  # Daha küçük pozisyon
    'tp_percent': 0.012,  # %1.2
    'sl_percent': 0.005,  # %0.5
    'weights': {
        'TRENDING_UP': 3.0,
        'OUTSIDE_BAR': 3.5,
        'TRENDING_DOWN': 2.0,
        'INSIDE_BAR': 0.3
    },
    'trade_management': {
        'use_trailing_stop': True,
        'trailing_stop_activation': 0.6,
        'trailing_stop_distance': 0.25,
        'use_breakeven': True,
        'breakeven_activation': 0.4,
        'breakeven_offset': 0.05,
        'use_partial_exit': False,
        'use_momentum_exit': False,
        'use_time_exit': False,
    },
    'commission': 0.0004,
}


# ALTERNATİF 2: Daha Konservatif (Daha az trade, yüksek kalite)
INTRADAY_CONSERVATIVE_CONFIG = {
    'name': 'Intraday Conservative (High Quality)',
    'timeframe': '15m',
    'entry_patterns': ['Trending Up', 'Outside Bar'],
    'min_strength': 50,  # Çok yüksek threshold
    'position_size': 0.12,  # Daha büyük pozisyon
    'tp_percent': 0.020,  # %2
    'sl_percent': 0.008,  # %0.8
    'weights': {
        'TRENDING_UP': 3.0,
        'OUTSIDE_BAR': 3.5,
        'TRENDING_DOWN': 2.0,
        'INSIDE_BAR': 0.3
    },
    'trade_management': {
        'use_trailing_stop': True,
        'trailing_stop_activation': 1.0,
        'trailing_stop_distance': 0.4,
        'use_breakeven': True,
        'breakeven_activation': 0.6,
        'breakeven_offset': 0.05,
        'use_partial_exit': False,
        'use_momentum_exit': False,
        'use_time_exit': False,
    },
    'commission': 0.0004,
}


# KARŞILAŞTIRMA TABLOSU
def print_comparison_table():
    """Tüm konfigürasyonları karşılaştır"""
    configs = [
        ('OPTIMIZED (Önerilen)', INTRADAY_OPTIMIZED_CONFIG),
        ('AGGRESSIVE (Fazla Trade)', INTRADAY_AGGRESSIVE_CONFIG),
        ('CONSERVATIVE (Az Trade)', INTRADAY_CONSERVATIVE_CONFIG),
    ]

    print("="*100)
    print("İNTRADAY KONFİGÜRASYON KARŞILAŞTIRMASI")
    print("="*100)
    print(f"\n{'Parametre':<25} {'Optimized':<25} {'Aggressive':<25} {'Conservative':<25}")
    print("-" * 100)

    params = [
        ('Min Strength', 'min_strength'),
        ('Position Size', 'position_size'),
        ('TP (%)', 'tp_percent'),
        ('SL (%)', 'sl_percent'),
        ('Trailing Act (%)', lambda c: c['trade_management']['trailing_stop_activation']),
        ('Trailing Dist (%)', lambda c: c['trade_management']['trailing_stop_distance']),
        ('Breakeven (%)', lambda c: c['trade_management']['breakeven_activation']),
    ]

    for label, key in params:
        values = []
        for _, config in configs:
            if callable(key):
                val = key(config)
            else:
                val = config[key]

            # Format değer
            if isinstance(val, float) and val < 1:
                values.append(f"{val*100:.2f}%")
            else:
                values.append(str(val))

        print(f"{label:<25} {values[0]:<25} {values[1]:<25} {values[2]:<25}")

    print("\n" + "="*100)
    print("\n📊 BEKLENEN PERFORMANS TAHMİNLERİ:")
    print("="*100)
    print(f"{'Config':<25} {'Trade/Ay':<15} {'Win Rate':<15} {'Avg Profit/Trade':<20} {'Risk/Reward':<15}")
    print("-" * 100)

    estimates = [
        ('OPTIMIZED', '50-70', '55-60%', '%0.8-1.0', '1:2.5'),
        ('AGGRESSIVE', '80-100', '50-55%', '%0.5-0.7', '1:2.4'),
        ('CONSERVATIVE', '30-40', '60-65%', '%1.0-1.2', '1:2.5'),
    ]

    for name, trades, wr, avg_profit, rr in estimates:
        print(f"{name:<25} {trades:<15} {wr:<15} {avg_profit:<20} {rr:<15}")

    print("\n" + "="*100)
    print("\n💡 ÖNERLER:")
    print("="*100)
    print("""
1. BAŞLANGIÇ İÇİN: OPTIMIZED config ile başla
   - Dengeli parametreler
   - Orta seviye trade sayısı
   - İyi risk/reward oranı

2. DAHA FAZLA TRADE İSTİYORSAN: AGGRESSIVE
   - Daha sık sinyal
   - Daha küçük pozisyonlar
   - Daha fazla komisyon maliyeti

3. KALİTE ÖNCELİĞİNDEYSEN: CONSERVATIVE
   - Az ama kaliteli trade
   - Daha büyük pozisyonlar
   - Daha yüksek win rate beklentisi

4. TEST ETME:
   Her 3 config'i de backtest et ve en iyi performansı seç!
    """)
    print("="*100)


if __name__ == '__main__':
    print_comparison_table()
