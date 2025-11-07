"""
Fractal Cascade System - Multi-Timeframe Fraktal Yapı Analizi

Piyasanın kalbi: Her zaman dilimindeki high-low ilişkisi,
bir sonraki zaman dilimini etkileyen fraktal bir yapı oluşturur.

Konsept:
- 1m'deki fraktal yapı → 5m'yi etkiler
- 5m'deki fraktal yapı → 15m'yi etkiler
- 15m'deki fraktal yapı → 1h'yi etkiler
- 1h'deki fraktal yapı → 4h'yi etkiler

Her seviye, bir önceki seviyenin "özeti" gibi davranır.
"""

import sys
from pathlib import Path

# fractal_analyzer'ı import et
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from fractal_analyzer import FractalPattern, FractalAnalyzer

from typing import List, Dict, Tuple, Optional
from enum import Enum
import pandas as pd
import numpy as np


class FractalCascadeLevel(Enum):
    """Fraktal cascade seviyeleri"""
    MICRO = "1m"       # Mikro seviye
    MINI = "5m"        # Mini seviye
    SHORT = "15m"      # Kısa seviye
    MEDIUM = "1h"      # Orta seviye
    LONG = "4h"        # Uzun seviye
    MACRO = "1d"       # Makro seviye


class FractalCascade:
    """
    Multi-timeframe fraktal cascade analiz sistemi.

    Her zaman dilimindeki fraktal yapı, bir sonraki zaman dilimini etkiler.
    Bu, piyasanın "kalp atışı" gibi düşünülebilir - her seviye bir öncekini etkiler.
    """

    # Cascade ağırlıkları (üst timeframe'ler daha etkili)
    CASCADE_WEIGHTS = {
        FractalCascadeLevel.MICRO: 0.05,   # %5 ağırlık
        FractalCascadeLevel.MINI: 0.10,    # %10 ağırlık
        FractalCascadeLevel.SHORT: 0.20,   # %20 ağırlık
        FractalCascadeLevel.MEDIUM: 0.30,  # %30 ağırlık
        FractalCascadeLevel.LONG: 0.25,    # %25 ağırlık
        FractalCascadeLevel.MACRO: 0.10,   # %10 ağırlık
    }

    # Pattern influence scores (bir pattern'in bir sonraki timeframe'e etkisi)
    PATTERN_INFLUENCE = {
        FractalPattern.OUTSIDE_BAR: 3.5,    # En güçlü etki (genişleme)
        FractalPattern.TRENDING_UP: 3.0,    # Güçlü yükseliş etkisi
        FractalPattern.TRENDING_DOWN: 2.0,  # Orta düşüş etkisi
        FractalPattern.INSIDE_BAR: 0.5,     # Zayıf etki (daralma)
        FractalPattern.UNKNOWN: 0.0,        # Etki yok
    }

    @staticmethod
    def analyze_cascade(
        timeframe_data: Dict[FractalCascadeLevel, pd.DataFrame]
    ) -> Dict[str, any]:
        """
        Multi-timeframe cascade analizi yap.

        Args:
            timeframe_data: Her timeframe için OHLCV DataFrame
                {
                    FractalCascadeLevel.SHORT: df_15m,
                    FractalCascadeLevel.MEDIUM: df_1h,
                    FractalCascadeLevel.LONG: df_4h,
                }

        Returns:
            Dict: Cascade analiz sonuçları
                {
                    'cascade_score': float,  # Toplam cascade skoru
                    'dominant_pattern': FractalPattern,
                    'timeframe_patterns': {...},
                    'cascade_strength': float,
                }
        """
        # Her timeframe için fraktal pattern tespit et
        timeframe_patterns = {}
        timeframe_strengths = {}

        for level, df in timeframe_data.items():
            if len(df) < 2:
                continue

            # Son iki mumu al
            prev = df.iloc[-2]
            curr = df.iloc[-1]

            # Pattern tespit
            pattern = FractalAnalyzer.analyze_candles(
                prev['high'], prev['low'],
                curr['high'], curr['low']
            )

            # Güç hesapla
            strength = FractalAnalyzer.calculate_strength(
                prev['high'], prev['low'],
                curr['high'], curr['low']
            )

            timeframe_patterns[level] = pattern
            timeframe_strengths[level] = strength

        # Cascade skoru hesapla
        cascade_score = FractalCascade._calculate_cascade_score(
            timeframe_patterns,
            timeframe_strengths
        )

        # Dominant pattern tespit et (en yüksek weighted influence)
        dominant_pattern = FractalCascade._find_dominant_pattern(
            timeframe_patterns
        )

        # Cascade strength (timeframe'ler arası uyum)
        cascade_strength = FractalCascade._calculate_cascade_strength(
            timeframe_patterns
        )

        return {
            'cascade_score': cascade_score,
            'dominant_pattern': dominant_pattern,
            'timeframe_patterns': timeframe_patterns,
            'timeframe_strengths': timeframe_strengths,
            'cascade_strength': cascade_strength,
        }

    @staticmethod
    def _calculate_cascade_score(
        patterns: Dict[FractalCascadeLevel, FractalPattern],
        strengths: Dict[FractalCascadeLevel, float]
    ) -> float:
        """
        Cascade skorunu hesapla.

        Her timeframe'in pattern'i, ağırlığına göre skora katkıda bulunur.
        """
        total_score = 0.0

        for level, pattern in patterns.items():
            # Pattern influence
            influence = FractalCascade.PATTERN_INFLUENCE.get(pattern, 0.0)

            # Timeframe weight
            weight = FractalCascade.CASCADE_WEIGHTS.get(level, 0.0)

            # Strength
            strength = strengths.get(level, 0.0) / 100.0  # Normalize 0-1

            # Contribution
            contribution = influence * weight * strength

            total_score += contribution

        return total_score

    @staticmethod
    def _find_dominant_pattern(
        patterns: Dict[FractalCascadeLevel, FractalPattern]
    ) -> FractalPattern:
        """En dominant pattern'i bul (en yüksek weighted influence)."""
        pattern_scores = {}

        for level, pattern in patterns.items():
            weight = FractalCascade.CASCADE_WEIGHTS.get(level, 0.0)
            influence = FractalCascade.PATTERN_INFLUENCE.get(pattern, 0.0)

            score = weight * influence

            if pattern not in pattern_scores:
                pattern_scores[pattern] = 0.0
            pattern_scores[pattern] += score

        if not pattern_scores:
            return FractalPattern.UNKNOWN

        dominant = max(pattern_scores.items(), key=lambda x: x[1])
        return dominant[0]

    @staticmethod
    def _calculate_cascade_strength(
        patterns: Dict[FractalCascadeLevel, FractalPattern]
    ) -> float:
        """
        Cascade gücü (timeframe'ler arası uyum).

        Tüm timeframe'lerde aynı pattern varsa = 1.0 (maksimum uyum)
        Farklı pattern'ler varsa = düşük skor
        """
        if not patterns:
            return 0.0

        pattern_list = list(patterns.values())

        # En yaygın pattern
        from collections import Counter
        pattern_counts = Counter(pattern_list)
        most_common_pattern, count = pattern_counts.most_common(1)[0]

        # Uyum oranı
        alignment = count / len(pattern_list)

        return alignment

    @staticmethod
    def get_cascade_signal(
        cascade_result: Dict[str, any],
        threshold: float = 5.0
    ) -> Tuple[int, str]:
        """
        Cascade analizinden sinyal üret.

        Args:
            cascade_result: analyze_cascade() sonucu
            threshold: Minimum cascade_score için threshold

        Returns:
            Tuple[int, str]: (Signal, Açıklama)
                Signal: 1 (LONG), -1 (SHORT), 0 (NEUTRAL)
        """
        score = cascade_result['cascade_score']
        dominant = cascade_result['dominant_pattern']
        strength = cascade_result['cascade_strength']

        # Yetersiz skor
        if score < threshold:
            return 0, f"Yetersiz cascade score: {score:.2f} < {threshold}"

        # Zayıf alignment
        if strength < 0.5:
            return 0, f"Düşük cascade alignment: {strength:.2%}"

        # Pattern'e göre sinyal
        if dominant == FractalPattern.TRENDING_UP:
            return 1, f"LONG: Trending Up dominant (score={score:.2f}, strength={strength:.2%})"

        elif dominant == FractalPattern.OUTSIDE_BAR:
            # Outside bar genelde momentum değişimi - dikkatli olunmalı
            # Bir üst timeframe'e bakarak karar ver
            return 0, "NEUTRAL: Outside Bar (momentum değişimi)"

        elif dominant == FractalPattern.TRENDING_DOWN:
            return -1, f"SHORT: Trending Down dominant (score={score:.2f}, strength={strength:.2%})"

        elif dominant == FractalPattern.INSIDE_BAR:
            return 0, "NEUTRAL: Inside Bar (konsolidasyon)"

        else:
            return 0, "NEUTRAL: Unknown pattern"

    @staticmethod
    def get_cascade_confidence(cascade_result: Dict[str, any]) -> float:
        """
        Cascade sinyalinin güven seviyesi (0-1 arası).

        Yüksek score + yüksek strength = yüksek güven
        """
        score = cascade_result['cascade_score']
        strength = cascade_result['cascade_strength']

        # Normalize score (0-10 arası olduğunu varsayalım)
        norm_score = min(score / 10.0, 1.0)

        # Confidence = score * strength
        confidence = norm_score * strength

        return confidence


def example_usage():
    """Örnek kullanım"""
    print("🧬 Fractal Cascade System - Örnek Kullanım\n")

    # Örnek veri (gerçekte Jesse'den gelecek)
    # 15m timeframe
    df_15m = pd.DataFrame({
        'high': [50000, 50500],
        'low': [49500, 49800],
        'close': [49800, 50200],
    })

    # 1h timeframe
    df_1h = pd.DataFrame({
        'high': [50000, 50800],
        'low': [49000, 49500],
        'close': [49500, 50300],
    })

    # 4h timeframe
    df_4h = pd.DataFrame({
        'high': [51000, 52000],
        'low': [48500, 50000],
        'close': [50000, 51500],
    })

    # Cascade analizi
    timeframe_data = {
        FractalCascadeLevel.SHORT: df_15m,
        FractalCascadeLevel.MEDIUM: df_1h,
        FractalCascadeLevel.LONG: df_4h,
    }

    result = FractalCascade.analyze_cascade(timeframe_data)

    print("📊 Cascade Analiz Sonuçları:")
    print(f"  Cascade Score: {result['cascade_score']:.2f}")
    print(f"  Dominant Pattern: {result['dominant_pattern'].value}")
    print(f"  Cascade Strength: {result['cascade_strength']:.2%}")
    print(f"\n  Timeframe Patterns:")
    for level, pattern in result['timeframe_patterns'].items():
        strength = result['timeframe_strengths'][level]
        print(f"    {level.value}: {pattern.value} (strength: {strength:.1f})")

    # Sinyal üret
    signal, explanation = FractalCascade.get_cascade_signal(result, threshold=3.0)
    confidence = FractalCascade.get_cascade_confidence(result)

    print(f"\n🎯 Sinyal: {signal}")
    print(f"  Açıklama: {explanation}")
    print(f"  Güven Seviyesi: {confidence:.2%}")


if __name__ == '__main__':
    example_usage()
