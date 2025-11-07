"""
STRATEGY FACTORY - Otomatik Strateji Üreteci
═══════════════════════════════════════════════════════════
Farklı algoritmaları kombinleyip otomatik test eder
Literatürdeki algoritmalar + kural kombinasyonları

(GÜNCELLENDİ: 5 YENİ FİLTRELENMİŞ FRAKTAL STRATEJİSİ EKLENDİ)
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from technical_indicators import TechnicalIndicators


# ══════════════════════════════════════════════════════════════════════════
# KURAL FONKSİYONLARI (PICKLE DOSTU)
# ══════════════════════════════════════════════════════════════════════════
# Tüm 'lambda' fonksiyonları, multiprocessing'in (pickle) çalışabilmesi için
# modülün en üst seviyesine 'def' ile tanımlanmıştır.
# ══════════════════════════════════════════════════════════════════════════

# ═══ FRACTAL KURALLARI ═══
def rule_fractal_trending_up(row):
    return row.get('fractal_pattern') == 'Trending Up' and row.get('fractal_strength', 0) >= 30

def rule_fractal_outside_bar(row):
    return row.get('fractal_pattern') == 'Outside Bar' and row.get('fractal_strength', 0) >= 30

def rule_fractal_strong(row):
    return row.get('fractal_strength', 0) >= 40

# YENİ EKLENDİ (Strateji #18 ve #19 için)
def rule_fractal_inside_bar(row):
    return row.get('fractal_pattern') == 'Inside Bar' and row.get('fractal_strength', 0) >= 30

# YENİ EKLENDİ (Strateji #19 için)
def rule_fractal_trending_down(row):
    return row.get('fractal_pattern') == 'Trending Down' and row.get('fractal_strength', 0) >= 30


# ═══ RSI KURALLARI ═══
def rule_rsi_oversold(row):
    return row.get('rsi', 50) < 30

def rule_rsi_overbought(row):
    return row.get('rsi', 50) > 70

def rule_rsi_bullish(row):
    return 40 < row.get('rsi', 50) < 60

# YENİ EKLENDİ (Strateji #16 için)
def rule_rsi_not_overbought(row):
    """RSI'ın aşırı alımda OLMADIĞINI kontrol et"""
    return row.get('rsi', 50) < 70

# ═══ MACD KURALLARI ═══
def rule_macd_bullish_cross(row):
    return (row.get('macd', 0) > row.get('signal', 0) and
            row.get('histogram', 0) > 0)

def rule_macd_bearish_cross(row):
    return (row.get('macd', 0) < row.get('signal', 0) and
            row.get('histogram', 0) < 0)

# ═══ BOLLINGER BANDS KURALLARI ═══
def rule_bb_lower_touch(row):
    return row.get('close', 0) <= row.get('bb_lower', 0) * 1.01

def rule_bb_upper_touch(row):
    return row.get('close', 0) >= row.get('bb_upper', 0) * 0.99

def rule_bb_squeeze(row):
    return row.get('bb_width', 1000) < row.get('atr', 500) * 2

# ═══ EMA/SMA KURALLARI ═══
def rule_ema_golden_cross(row):
    return (row.get('ema_9', 0) > row.get('ema_21', 0) and
            row.get('ema_21', 0) > row.get('ema_50', 0))

def rule_ema_death_cross(row):
    return (row.get('ema_9', 0) < row.get('ema_21', 0) and
            row.get('ema_21', 0) < row.get('ema_50', 0))

def rule_price_above_ema(row):
    return row.get('close', 0) > row.get('ema_50', 0)

# ═══ STOCHASTIC KURALLARI ═══
def rule_stoch_oversold(row):
    return row.get('stoch_k', 50) < 20 and row.get('stoch_d', 50) < 20

def rule_stoch_overbought(row):
    return row.get('stoch_k', 50) > 80 and row.get('stoch_d', 50) > 80

# ═══ ADX KURALLARI ═══
def rule_adx_strong_trend(row):
    return row.get('adx', 0) > 25

def rule_adx_uptrend(row):
    return (row.get('adx', 0) > 25 and
            row.get('plus_di', 0) > row.get('minus_di', 0))

# ═══ VOLUME KURALLARI ═══
def rule_volume_spike(row):
    return row.get('volume', 0) > row.get('volume_ma', 1) * 1.5

def rule_volume_above_avg(row):
    return row.get('volume', 0) > row.get('volume_ma', 1)

# ══════════════════════════════════════════════════════════════════════════
# SINIFLAR
# ══════════════════════════════════════════════════════════════════════════

class StrategyRule:
    """Tek bir kural"""
    def __init__(self, name, check_func, description):
        self.name = name
        self.check_func = check_func
        self.description = description

    def check(self, row):
        """Kuralı kontrol et"""
        return self.check_func(row)


class Strategy:
    """Birden fazla kuraldan oluşan strateji"""
    def __init__(self, name, rules, require_all=True):
        self.name = name
        self.rules = rules
        self.require_all = require_all  # True: AND, False: OR

    def check_entry(self, row):
        """Giriş sinyali kontrol"""
        results = [rule.check(row) for rule in self.rules]

        if self.require_all:
            return all(results)  # Tüm kurallar doğru olmalı (AND)
        else:
            return any(results)  # En az bir kural doğru olmalı (OR)


class StrategyFactory:
    """Strateji fabrikası - otomatik strateji üretir"""

    def __init__(self):
        self.strategies = []

    @staticmethod
    def create_rules():
        """Tüm kuralları oluştur"""
        rules = {}

        # ═══ FRACTAL KURALLARI ═══
        rules['fractal_trending_up'] = StrategyRule(
            'Fractal Trending Up',
            rule_fractal_trending_up,
            'Fraktal yükseliş trendi'
        )
        rules['fractal_outside_bar'] = StrategyRule(
            'Fractal Outside Bar',
            rule_fractal_outside_bar,
            'Fraktal outside bar'
        )
        rules['fractal_strong'] = StrategyRule(
            'Fractal Strong',
            rule_fractal_strong,
            'Güçlü fraktal sinyali (40+)'
        )
        # YENİ EKLENDİ
        rules['fractal_inside_bar'] = StrategyRule(
            'Fractal Inside Bar',
            rule_fractal_inside_bar,
            'Fraktal inside bar'
        )
        # YENİ EKLENDİ
        rules['fractal_trending_down'] = StrategyRule(
            'Fractal Trending Down',
            rule_fractal_trending_down,
            'Fraktal düşüş trendi'
        )

        # ═══ RSI KURALLARI ═══
        rules['rsi_oversold'] = StrategyRule(
            'RSI Oversold',
            rule_rsi_oversold,
            'RSI aşırı satım (<30)'
        )
        rules['rsi_overbought'] = StrategyRule(
            'RSI Overbought',
            rule_rsi_overbought,
            'RSI aşırı alım (>70)'
        )
        rules['rsi_bullish'] = StrategyRule(
            'RSI Bullish',
            rule_rsi_bullish,
            'RSI yükseliş bölgesinde (40-60)'
        )
        # YENİ EKLENDİ
        rules['rsi_not_overbought'] = StrategyRule(
            'RSI Not Overbought',
            rule_rsi_not_overbought,
            'RSI aşırı alım DEĞİL (<70)'
        )

        # ═══ MACD KURALLARI ═══
        rules['macd_bullish_cross'] = StrategyRule(
            'MACD Bullish Cross',
            rule_macd_bullish_cross,
            'MACD yükseliş kesişimi'
        )
        rules['macd_bearish_cross'] = StrategyRule(
            'MACD Bearish Cross',
            rule_macd_bearish_cross,
            'MACD düşüş kesişimi'
        )

        # ═══ BOLLINGER BANDS KURALLARI ═══
        rules['bb_lower_touch'] = StrategyRule(
            'BB Lower Band Touch',
            rule_bb_lower_touch,
            'Bollinger alt banda değdi'
        )
        rules['bb_upper_touch'] = StrategyRule(
            'BB Upper Band Touch',
            rule_bb_upper_touch,
            'Bollinger üst banda değdi'
        )
        rules['bb_squeeze'] = StrategyRule(
            'BB Squeeze',
            rule_bb_squeeze,
            'Bollinger sıkışması (düşük volatilite)'
        )

        # ═══ EMA/SMA KURALLARI ═══
        rules['ema_golden_cross'] = StrategyRule(
            'EMA Golden Cross',
            rule_ema_golden_cross,
            'EMA altın kesişim (9>21>50)'
        )
        rules['ema_death_cross'] = StrategyRule(
            'EMA Death Cross',
            rule_ema_death_cross,
            'EMA ölüm kesişimi (9<21<50)'
        )
        rules['price_above_ema'] = StrategyRule(
            'Price Above EMA',
            rule_price_above_ema,
            'Fiyat EMA50 üstünde'
        )

        # ═══ STOCHASTIC KURALLARI ═══
        rules['stoch_oversold'] = StrategyRule(
            'Stochastic Oversold',
            rule_stoch_oversold,
            'Stochastic aşırı satım (<20)'
        )
        rules['stoch_overbought'] = StrategyRule(
            'Stochastic Overbought',
            rule_stoch_overbought,
            'Stochastic aşırı alım (>80)'
        )

        # ═══ ADX KURALLARI ═══
        rules['adx_strong_trend'] = StrategyRule(
            'ADX Strong Trend',
            rule_adx_strong_trend,
            'Güçlü trend (ADX>25)'
        )
        rules['adx_uptrend'] = StrategyRule(
            'ADX Uptrend',
            rule_adx_uptrend,
            'ADX yükseliş trendi'
        )

        # ═══ VOLUME KURALLARI ═══
        rules['volume_spike'] = StrategyRule(
            'Volume Spike',
            rule_volume_spike,
            'Hacim patlaması (1.5x)'
        )
        rules['volume_above_avg'] = StrategyRule(
            'Volume Above Average',
            rule_volume_above_avg,
            'Hacim ortalamanın üstünde'
        )

        return rules

    def generate_strategies(self):
        """Farklı kombinasyonlarda stratejiler üret"""
        rules = self.create_rules()

        # ═══ POPÜLER KOMBİNASYONLAR (1-15) ═══

        # 1. Fractal + RSI Oversold
        self.strategies.append(Strategy(
            'Fractal + RSI Oversold',
            [rules['fractal_trending_up'], rules['rsi_oversold']],
            require_all=True
        ))
        # 2. Fractal + MACD Bullish
        self.strategies.append(Strategy(
            'Fractal + MACD Bullish',
            [rules['fractal_trending_up'], rules['macd_bullish_cross']],
            require_all=True
        ))
        # 3. Fractal + Bollinger Lower
        self.strategies.append(Strategy(
            'Fractal + BB Lower',
            [rules['fractal_trending_up'], rules['bb_lower_touch']],
            require_all=True
        ))
        # 4. Fractal + EMA Golden Cross
        self.strategies.append(Strategy(
            'Fractal + EMA Golden',
            [rules['fractal_trending_up'], rules['ema_golden_cross']],
            require_all=True
        ))
        # 5. RSI + MACD (klasik)
        self.strategies.append(Strategy(
            'RSI + MACD Classic',
            [rules['rsi_oversold'], rules['macd_bullish_cross']],
            require_all=True
        ))
        # 6. Bollinger + Volume Spike
        self.strategies.append(Strategy(
            'BB Lower + Volume Spike',
            [rules['bb_lower_touch'], rules['volume_spike']],
            require_all=True
        ))
        # 7. Triple Confirmation (3 kural)
        self.strategies.append(Strategy(
            'Triple Confirmation',
            [rules['fractal_trending_up'], rules['rsi_oversold'], rules['macd_bullish_cross']],
            require_all=True
        ))
        # 8. EMA + ADX + Volume
        self.strategies.append(Strategy(
            'EMA + ADX + Volume',
            [rules['ema_golden_cross'], rules['adx_strong_trend'], rules['volume_above_avg']],
            require_all=True
        ))
        # 9. Stochastic + Bollinger
        self.strategies.append(Strategy(
            'Stochastic + BB',
            [rules['stoch_oversold'], rules['bb_lower_touch']],
            require_all=True
        ))
        # 10. Fractal Outside Bar + Volume
        self.strategies.append(Strategy(
            'Outside Bar + Volume',
            [rules['fractal_outside_bar'], rules['volume_spike']],
            require_all=True
        ))
        # 11. Multi-Indicator Confluence (4 kural)
        self.strategies.append(Strategy(
            'Multi-Indicator Confluence',
            [rules['fractal_trending_up'], rules['price_above_ema'],
             rules['adx_uptrend'], rules['volume_above_avg']],
            require_all=True
        ))
        # 12. Squeeze Breakout
        self.strategies.append(Strategy(
            'Squeeze Breakout',
            [rules['bb_squeeze'], rules['volume_spike'], rules['fractal_strong']],
            require_all=True
        ))
        # 13. Fractal Only (baseline)
        self.strategies.append(Strategy(
            'Fractal Only',
            [rules['fractal_trending_up']],
            require_all=True
        ))
        # 14. RSI + EMA
        self.strategies.append(Strategy(
            'RSI + EMA Trend',
            [rules['rsi_bullish'], rules['ema_golden_cross']],
            require_all=True
        ))
        # 15. ADX Trend Following
        self.strategies.append(Strategy(
            'ADX Trend Following',
            [rules['adx_uptrend'], rules['price_above_ema'], rules['volume_above_avg']],
            require_all=True
        ))

        # ══════════════════════════════════════════
        # ═══ YENİ FRAKTAL ODAKLI STRATEJİLER (16-20) ═══
        # ══════════════════════════════════════════

        # 16. Fractal Trend Rider (Trend + Momentum Filtreli)
        self.strategies.append(Strategy(
            '[F] Fractal Trend Rider',
            [
                rules['price_above_ema'],       # 1. Ana trend YUKARI
                rules['fractal_trending_up'],   # 2. Momentum sinyali GELDİ
                rules['rsi_not_overbought']     # 3. Pazar henüz şişmedi (RSI < 70)
            ],
            require_all=True
        ))

        # 17. Fractal Volume Breakout (Momentum + Hacim Teyitli)
        self.strategies.append(Strategy(
            '[F] Fractal Volume Breakout',
            [
                rules['fractal_outside_bar'],   # 1. Genişleme (Outside Bar)
                rules['volume_spike']           # 2. Hacim patlaması ile teyitli
            ],
            require_all=True
        ))

        # 18. Fractal Mean Reversion (Tersine Dönüş / Destek)
        self.strategies.append(Strategy(
            '[F] Fractal Mean Reversion',
            [
                rules['fractal_inside_bar'],    # 1. Daralma / Kararsızlık
                rules['bb_lower_touch']         # 2. Bollinger Alt Bandı (Destek)
            ],
            require_all=True
        ))

        # 19. Fractal Exhaustion Dip (Tersine Dönüş / Dip Alımı)
        self.strategies.append(Strategy(
            '[F] Fractal Exhaustion Dip',
            [
                rules['fractal_trending_down'], # 1. Fiyat düşüyor...
                rules['rsi_oversold']           # 2. ...ama artık aşırı satımda (RSI < 30)
            ],
            require_all=True
        ))

        # 20. Fractal ADX Confirmed (Güçlü Trend Teyitli)
        self.strategies.append(Strategy(
            '[F] Fractal ADX Confirmed',
            [
                rules['fractal_trending_up'],   # 1. Yükseliş sinyali
                rules['adx_uptrend']            # 2. ADX güçlü yükseliş trendi teyidi
            ],
            require_all=True
        ))

        print(f"✅ {len(self.strategies)} strateji oluşturuldu! (15 eski + 5 YENİ Fraktal)")
        return self.strategies

    def list_strategies(self):
        """Stratejileri listele"""
        print("\n" + "="*80)
        print("OLUŞTURULAN STRATEJİLER")
        print("="*80 + "\n")

        for i, strategy in enumerate(self.strategies, 1):
            print(f"{i}. {strategy.name}")
            print(f"   Kurallar: {', '.join([r.name for r in strategy.rules])}")
            print(f"   Tip: {'AND (hepsi gerekli)' if strategy.require_all else 'OR (en az biri)'}")
            print()


if __name__ == '__main__':
    print("\n" + "="*80)
    print("STRATEGY FACTORY - Otomatik Strateji Üreteci")
    print("="*80)

    factory = StrategyFactory()
    strategies = factory.generate_strategies()
    factory.list_strategies()

    print("="*80)
    print(f"\n🚀 Toplam {len(strategies)} strateji test edilmeye hazır!")
    print("\nBu stratejileri test etmek için:")
    print("  python strategy_batch_tester.py")
    print("="*80)