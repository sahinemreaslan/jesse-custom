"""
INTRADAY TRAILING STOP MASTER - Gün İçi Trade Konfigürasyonu
═══════════════════════════════════════════════════════════
Timeframe: 15 dakika
Hedef: Günde 3-5 trade, hızlı giriş/çıkış

FARKLAR (1h versiyonuna göre):
  TP: %30 → %2 (15x daha küçük!)
  SL: %8 → %1 (8x daha küçük!)
  Trailing Activation: %5 → %1
  Trailing Distance: %3.5 → %0.5
  Breakeven: %3 → %0.5

SONUÇ:
  - Daha sık trade
  - Daha hızlı kar alma
  - Daha sıkı risk kontrolü
  - Günlük %2-5 hedef
═══════════════════════════════════════════════════════════
"""

# INTRADAY STRATEJİ KONFIGÜRASYONU
INTRADAY_CONFIG = {
    'name': 'Intraday Trailing Stop Master',
    'timeframe': '15m',  # 15 dakika

    # Giriş kuralları (aynı)
    'entry_patterns': ['Trending Up', 'Outside Bar'],
    'min_strength': 30,  # Pattern gücü minimum 30

    # Pozisyon boyutu
    'position_size': 0.15,  # %15 sermaye

    # INTRADAY: Küçük TP/SL!
    'tp_percent': 0.03,   # %2 kar hedefi (önceden %30!)
    'sl_percent': 0.01,   # %1 zarar durdurma (önceden %8!)

    # Fraktal ağırlıkları (aynı)
    'weights': {
        'TRENDING_UP': 3.0,
        'OUTSIDE_BAR': 3.5,
        'TRENDING_DOWN': 2.0,
        'INSIDE_BAR': 0.3
    },

    # INTRADAY: Sıkı trailing stop!
    'trade_management': {
        # Trailing Stop
        'use_trailing_stop': True,
        'trailing_stop_activation': 2.0,    # %1 kârda aktif (önceden %5!)
        'trailing_stop_distance': 1.0,      # %0.5 mesafe (önceden %3.5!)

        # Breakeven
        'use_breakeven': True,
        'breakeven_activation': 1.5,        # %1.5 kâra ulaşınca aktifleştir
        'breakeven_offset': 0.1,            # stop'u +%0.1'e çek

        # Partial Exit (İsteğe bağlı)
        'use_partial_exit': True,
        'partial_exit_levels': [
            {'price_pct': 1.0, 'qty_pct': 0.5},   # %1 kârda yarısını sat
        ],

        # Diğerleri kapalı
        'use_momentum_exit': False,
        'use_time_exit': False,
    }
}


# KARŞILAŞTIRMA TABLOSU
COMPARISON = {
    '1h (Swing Trading)': {
        'timeframe': '1 hour',
        'tp': '%30',
        'sl': '%8',
        'trailing_activation': '%5',
        'trailing_distance': '%3.5',
        'trades_per_month': '~10',
        'avg_trade_duration': '2-7 days',
        'risk_reward': '1:3.75'
    },
    '15m (Intraday Trading)': {
        'timeframe': '15 minutes',
        'tp': '%2',
        'sl': '%1',
        'trailing_activation': '%1',
        'trailing_distance': '%0.5',
        'trades_per_month': '~50-100',
        'avg_trade_duration': '30min - 4hours',
        'risk_reward': '1:2'
    }
}


def print_comparison():
    """Karşılaştırma tablosunu yazdır"""
    print("="*80)
    print("STRATEJİ KARŞILAŞTIRMASI: 1H vs 15M")
    print("="*80)

    print(f"\n{'Parametre':<25} {'1H (Swing)':<25} {'15M (Intraday)':<25}")
    print("─" * 80)

    params = [
        ('Timeframe', 'timeframe'),
        ('Take Profit', 'tp'),
        ('Stop Loss', 'sl'),
        ('Trailing Activation', 'trailing_activation'),
        ('Trailing Distance', 'trailing_distance'),
        ('Trades/Month', 'trades_per_month'),
        ('Avg Duration', 'avg_trade_duration'),
        ('Risk/Reward', 'risk_reward'),
    ]

    for label, key in params:
        swing = COMPARISON['1h (Swing Trading)'][key]
        intraday = COMPARISON['15m (Intraday Trading)'][key]
        print(f"{label:<25} {swing:<25} {intraday:<25}")

    print("\n" + "="*80)
    print("🎯 INTRADAY AVANTAJLARI:")
    print("="*80)
    print("""
✅ Daha sık trade → Daha fazla fırsat
✅ Hızlı kar alma → Gün içinde kapatılan pozisyonlar
✅ Düşük sermaye gereksimi → Küçük fiyat hareketleri yeterli
✅ Overnight riski YOK → Gece pozisyon açık kalmaz
✅ Daha fazla veri → Hızlı öğrenme

⚠️ INTRADAY ZORLUKLAR:
⚠️ Daha fazla komisyon → Sık trade = daha fazla maliyet
⚠️ Daha fazla stres → Sürekli takip gerekli
⚠️ Daha az kar/trade → %2 vs %30
⚠️ Slippage etkisi → Hızlı hareketlerde kayma olabilir
    """)
    print("="*80)


if __name__ == '__main__':
    print_comparison()

    print("\n📋 INTRADAY STRATEJİ DETAYLARI:")
    print("="*80)
    for key, value in INTRADAY_CONFIG.items():
        if key != 'trade_management' and key != 'weights':
            print(f"  {key:25} = {value}")

    print("\n📊 Trade Management:")
    for key, value in INTRADAY_CONFIG['trade_management'].items():
        print(f"  {key:30} = {value}")
