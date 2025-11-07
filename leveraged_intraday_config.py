"""
LEVERAGED INTRADAY STRATEGY CONFIG
═══════════════════════════════════════════════════════════
Gün içi kaldıraçlı trade için optimize edilmiş konfigürasyon

TEMEL PRENSİPLER:
1. Sadece 1h timeframe (win rate %63.4)
2. Kaldıraç 3x-5x (daha yüksek riskli)
3. Pozisyonlar gün sonunda MUTLAKA kapatılır
4. Daha sıkı risk yönetimi
5. Position size küçültüldü

RİSK UYARISI:
⚠️ Kaldıraç kazancı ve kaybı katlar!
⚠️ Sadece risk alabileceğin sermaye ile kullan
⚠️ 5x kaldıraçta %2 kayıp = -%10 gerçek kayıp!
═══════════════════════════════════════════════════════════
"""

# KALDIRAÇ SEVİYELERİ
LEVERAGE_LEVELS = {
    'conservative': 2,    # Muhafazakar: 2x
    'moderate': 3,        # Orta: 3x
    'aggressive': 5,      # Agresif: 5x
    'very_aggressive': 10 # Çok Agresif: 10x (ÖNERİLMEZ!)
}

# BASE CONFIG (1h stratejiden alındı)
BASE_1H_CONFIG = {
    'timeframe': '1h',
    'entry_patterns': ['Trending Up', 'Outside Bar'],
    'min_strength': 30,
    'weights': {
        'TRENDING_UP': 3.0,
        'OUTSIDE_BAR': 3.5,
        'TRENDING_DOWN': 2.0,
        'INSIDE_BAR': 0.3
    },
}

# ═══════════════════════════════════════════════════════════
# KALDIRAÇ 2X - MUHAFAZAKAR (ÖNERİLİR YENİ BAŞLAYANLAR İÇİN)
# ═══════════════════════════════════════════════════════════
LEVERAGED_2X_CONFIG = {
    **BASE_1H_CONFIG,
    'name': 'Leveraged Intraday 2x (Conservative)',
    'leverage': 2,

    # Position Size: Kaldıraçla birlikte gerçek pozisyon
    'position_size': 0.10,  # %10 sermaye × 2x = %20 pozisyon

    # TP/SL: Kaldıraçlı, bu yüzden daha dar
    'tp_percent': 0.15,     # %15 (kaldıraçsız %30'dan yarıya indirildi)
    'sl_percent': 0.04,     # %4 (kaldıraçsız %8'den yarıya indirildi)

    # Trade Management
    'trade_management': {
        # Trailing Stop
        'use_trailing_stop': True,
        'trailing_stop_activation': 2.5,    # %2.5 kârda aktif (yarıya indirildi)
        'trailing_stop_distance': 1.75,     # %1.75 mesafe (yarıya indirildi)

        # Breakeven (daha erken!)
        'use_breakeven': True,
        'breakeven_activation': 1.5,        # %1.5 kârda aktif (yarıya indirildi)
        'breakeven_offset': 0.25,

        # Time-based Exit (GÜN İÇİ İÇİN KRİTİK!)
        'use_time_exit': True,
        'max_hold_hours': 14,               # Maksimum 14 saat tut
        'force_exit_time': '23:00',         # Saat 23:00'te zorla kapat

        # Partial Exit
        'use_partial_exit': True,
        'partial_exit_levels': [
            {'price_pct': 7.5, 'qty_pct': 0.5},   # %7.5 kârda yarısını sat
        ],

        'use_momentum_exit': False,
    },

    # Komisyon
    'commission': 0.0004,  # Binance Futures

    # Risk Limitleri
    'max_daily_trades': 3,           # Günde max 3 trade
    'max_daily_loss_pct': 5,         # Günlük max %5 kayıp (gerçek sermaye)
    'min_risk_reward': 2.5,          # Minimum R/R oranı
}

# ═══════════════════════════════════════════════════════════
# KALDIRAÇ 3X - ORTA (DENEYİMLİLER İÇİN)
# ═══════════════════════════════════════════════════════════
LEVERAGED_3X_CONFIG = {
    **BASE_1H_CONFIG,
    'name': 'Leveraged Intraday 3x (Moderate)',
    'leverage': 3,

    'position_size': 0.08,  # %8 sermaye × 3x = %24 pozisyon

    'tp_percent': 0.10,     # %10
    'sl_percent': 0.027,    # %2.7

    'trade_management': {
        'use_trailing_stop': True,
        'trailing_stop_activation': 1.67,   # %1.67
        'trailing_stop_distance': 1.17,     # %1.17

        'use_breakeven': True,
        'breakeven_activation': 1.0,        # %1 kârda aktif
        'breakeven_offset': 0.17,

        'use_time_exit': True,
        'max_hold_hours': 12,
        'force_exit_time': '23:00',

        'use_partial_exit': True,
        'partial_exit_levels': [
            {'price_pct': 5.0, 'qty_pct': 0.5},
        ],

        'use_momentum_exit': False,
    },

    'commission': 0.0004,
    'max_daily_trades': 2,
    'max_daily_loss_pct': 4,
    'min_risk_reward': 3.0,
}

# ═══════════════════════════════════════════════════════════
# KALDIRAÇ 5X - AGRESİF (SADECE UZMANLAR İÇİN!)
# ═══════════════════════════════════════════════════════════
LEVERAGED_5X_CONFIG = {
    **BASE_1H_CONFIG,
    'name': 'Leveraged Intraday 5x (Aggressive)',
    'leverage': 5,

    'position_size': 0.06,  # %6 sermaye × 5x = %30 pozisyon

    'tp_percent': 0.06,     # %6
    'sl_percent': 0.016,    # %1.6

    'trade_management': {
        'use_trailing_stop': True,
        'trailing_stop_activation': 1.0,    # %1
        'trailing_stop_distance': 0.7,      # %0.7

        'use_breakeven': True,
        'breakeven_activation': 0.6,        # %0.6 kârda aktif
        'breakeven_offset': 0.1,

        'use_time_exit': True,
        'max_hold_hours': 10,
        'force_exit_time': '23:00',

        'use_partial_exit': True,
        'partial_exit_levels': [
            {'price_pct': 3.0, 'qty_pct': 0.5},
        ],

        'use_momentum_exit': False,
    },

    'commission': 0.0004,
    'max_daily_trades': 1,           # Günde SADECE 1 trade!
    'max_daily_loss_pct': 3,
    'min_risk_reward': 3.5,
}


# ═══════════════════════════════════════════════════════════
# KARŞILAŞTIRMA VE RİSK ANALİZİ
# ═══════════════════════════════════════════════════════════

def print_leverage_comparison():
    """Kaldıraç seviyelerini karşılaştır"""
    print("="*100)
    print("KALDIRAÇ SEVİYELERİ KARŞILAŞTIRMASI")
    print("="*100)

    configs = [
        ('Kaldıraçsız (1h Original)', {
            'leverage': 1,
            'position_size': 0.15,
            'tp': 0.30,
            'sl': 0.08,
            'real_position': 15,
            'max_loss_per_trade': -1.2,
            'max_gain_per_trade': 4.5,
        }),
        ('2x Kaldıraç', {
            'leverage': 2,
            'position_size': 0.10,
            'tp': 0.15,
            'sl': 0.04,
            'real_position': 20,
            'max_loss_per_trade': -0.8,
            'max_gain_per_trade': 3.0,
        }),
        ('3x Kaldıraç', {
            'leverage': 3,
            'position_size': 0.08,
            'tp': 0.10,
            'sl': 0.027,
            'real_position': 24,
            'max_loss_per_trade': -0.65,
            'max_gain_per_trade': 2.4,
        }),
        ('5x Kaldıraç', {
            'leverage': 5,
            'position_size': 0.06,
            'tp': 0.06,
            'sl': 0.016,
            'real_position': 30,
            'max_loss_per_trade': -0.48,
            'max_gain_per_trade': 1.8,
        }),
    ]

    print(f"\n{'Config':<25} {'Kaldıraç':<12} {'Pos%':<10} {'TP%':<10} {'SL%':<10} "
          f"{'Gerçek Pos%':<15} {'Max Kayıp':<12} {'Max Kazanç':<12}")
    print("-" * 100)

    for name, cfg in configs:
        print(f"{name:<25} "
              f"{cfg['leverage']}x{'':<10} "
              f"{cfg['position_size']*100:.0f}%{'':<7} "
              f"{cfg['tp']*100:.1f}%{'':<6} "
              f"{cfg['sl']*100:.2f}%{'':<5} "
              f"{cfg['real_position']:.0f}%{'':<12} "
              f"{cfg['max_loss_per_trade']:+.2f}%{'':<7} "
              f"{cfg['max_gain_per_trade']:+.2f}%")

    print("\n" + "="*100)
    print("📊 RİSK/KAZANÇ ANALİZİ")
    print("="*100)

    print("""
1. KALDIRAÇSIZ (1x) - Original Strateji:
   ✅ En güvenli
   ✅ Büyük TP/SL marjı
   ❌ Daha az kazanç potansiyeli
   ❌ Pozisyonlar günlerce açık kalabilir (overnight risk)

   Örnek: $10,000 sermaye
   - Trade başına risk: $120
   - Trade başına max kazanç: $450
   - Uygun: Swing trading, sabırlı yatırımcılar

2. KALDIRAÇ 2X - MUHAFAZAKAR (ÖNERİLİR!):
   ✅ Dengeli risk/kazanç
   ✅ Gün sonunda pozisyon kapanır
   ✅ Daha sıkı stop loss
   ⚠️  Kaldıraçlı ama kontrollü

   Örnek: $10,000 sermaye
   - Trade başına risk: $80 (2x kaldıraçla $160 kayıp riski)
   - Trade başına max kazanç: $300
   - Uygun: Gün içi trading, orta risk toleransı

3. KALDIRAÇ 3X - ORTA:
   ⚠️  Orta-yüksek risk
   ✅ İyi kazanç potansiyeli
   ❌ Daha dar stop loss (noise'dan tetiklenebilir)
   ❌ Günde max 2 trade

   Örnek: $10,000 sermaye
   - Trade başına risk: $65 (3x kaldıraçla $195 kayıp riski)
   - Trade başına max kazanç: $240
   - Uygun: Deneyimli traderlar, aktif takip

4. KALDIRAÇ 5X - AGRESİF (RİSKLİ!):
   ❌ Yüksek risk!
   ❌ Çok dar stop loss
   ❌ Günde SADECE 1 trade
   ✅ Hızlı kazanç potansiyeli
   ⚠️  Liquidation riski var!

   Örnek: $10,000 sermaye
   - Trade başına risk: $48 (5x kaldıraçla $240 kayıp riski)
   - Trade başına max kazanç: $180
   - Uygun: SADECE uzmanlar, çok dikkatli takip
    """)

    print("="*100)
    print("\n⚠️  ÖNEMLİ RİSK UYARILARI:")
    print("="*100)
    print("""
1. LİQUİDATİON RİSKİ:
   - 5x kaldıraçta ~%20 ters hareket = Liquidation!
   - 3x kaldıraçta ~%33 ters hareket = Liquidation!
   - 2x kaldıraçta ~%50 ters hareket = Liquidation!

2. KOMİSYON:
   - Kaldıraçlı pozisyonlarda komisyon gerçek pozisyon üzerinden
   - 5x kaldıraçta komisyon 5x daha pahalı

3. FUNDING RATE (Binance Futures):
   - Her 8 saatte bir ödeme/alma
   - Pozisyonu 24 saatten fazla tutma!

4. VOLATİLİTE:
   - Bitcoin'de %5 hareket normal
   - 5x kaldıraçta %5 = %25 kayıp/kazanç!

5. PSİKOLOJİK FAKTÖR:
   - Kaldıraç stress'i artırır
   - Duygusal kararlar almanın önüne geç
   - Stop loss'u ASLA değiştirme
    """)

    print("="*100)
    print("✅ BENİM ÖNERİM:")
    print("="*100)
    print("""
1. YENİ BAŞLAYANLAR:
   → 2x kaldıraç ile başla
   → İlk ay paper trading
   → Sonra $100-500 ile gerçek test

2. DENEYİMLİLER:
   → 3x kaldıraç
   → Sıkı risk yönetimi
   → Günlük stop loss limiti

3. UZMANLAR:
   → 5x kaldıraca kadar
   → Ama asla 10x+ kullanma!
   → %1 kural: Asla toplam sermayenin %1'inden fazlasını riske atma
    """)
    print("="*100)


def calculate_position_size(balance, leverage, risk_pct=1.0):
    """
    Kaldıraçlı pozisyon boyutu hesapla

    Args:
        balance: Toplam sermaye
        leverage: Kaldıraç seviyesi (2, 3, 5, vb.)
        risk_pct: Trade başına risk yüzdesi (varsayılan %1)

    Returns:
        dict: Pozisyon detayları
    """
    # %1 kuralı: Trade başına max risk
    max_risk_amount = balance * (risk_pct / 100)

    # Örnek hesaplama (TP %15, SL %4 için 2x kaldıraç)
    configs = {
        2: {'tp': 0.15, 'sl': 0.04},
        3: {'tp': 0.10, 'sl': 0.027},
        5: {'tp': 0.06, 'sl': 0.016},
    }

    if leverage not in configs:
        raise ValueError(f"Desteklenmeyen kaldıraç: {leverage}")

    cfg = configs[leverage]

    # Position size hesapla
    # max_risk = position_size * balance * sl_pct
    # position_size = max_risk / (balance * sl_pct)
    position_size_pct = risk_pct / (cfg['sl'] * 100)
    position_size_amount = balance * (position_size_pct / 100)

    # Kaldıraçlı gerçek pozisyon
    real_position = position_size_amount * leverage

    return {
        'balance': balance,
        'leverage': leverage,
        'risk_pct': risk_pct,
        'risk_amount': max_risk_amount,
        'position_size_pct': position_size_pct,
        'position_size_amount': position_size_amount,
        'real_position_amount': real_position,
        'tp_pct': cfg['tp'] * 100,
        'sl_pct': cfg['sl'] * 100,
        'max_gain': position_size_amount * cfg['tp'],
        'max_loss': position_size_amount * cfg['sl'],
    }


if __name__ == '__main__':
    print_leverage_comparison()

    print("\n" + "="*100)
    print("ÖRNEK POZİSYON HESAPLAMALARI")
    print("="*100)

    balance = 10000

    for lev in [2, 3, 5]:
        print(f"\n{'='*100}")
        print(f"KALDIRAÇ {lev}X - $10,000 SERMAYE")
        print(f"{'='*100}")

        pos = calculate_position_size(balance, lev, risk_pct=1.0)

        print(f"""
Sermaye: ${pos['balance']:,.2f}
Kaldıraç: {pos['leverage']}x
Trade Başına Risk: %{pos['risk_pct']} (${pos['risk_amount']:,.2f})

Pozisyon Boyutu: %{pos['position_size_pct']:.2f} (${pos['position_size_amount']:,.2f})
Gerçek Pozisyon (Kaldıraçlı): ${pos['real_position_amount']:,.2f}

TP: %{pos['tp_pct']} → Max Kazanç: ${pos['max_gain']:,.2f}
SL: %{pos['sl_pct']} → Max Kayıp: ${pos['max_loss']:,.2f}

Risk/Reward: 1:{pos['max_gain']/pos['max_loss']:.2f}
        """)

    print("="*100)
