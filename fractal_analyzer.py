"""
Fraktal Yapı Analiz Motoru
İki mum arasındaki ilişkiyi 4 temel kuralla analiz eder
"""
import numpy as np
import pandas as pd
from enum import Enum
from typing import Tuple, Dict


class FractalPattern(Enum):
    """Fraktal patern tipleri"""
    INSIDE_BAR = "Inside Bar"      # Daralma / Kararsızlık
    OUTSIDE_BAR = "Outside Bar"    # Genişleme / Güçlü Momentum
    TRENDING_UP = "Trending Up"    # Yükseliş Momentumu
    TRENDING_DOWN = "Trending Down" # Düşüş Momentumu
    UNKNOWN = "Unknown"            # Tanımsız


class FractalAnalyzer:
    """
    Fraktal yapı analiz motoru
    Her iki mum için 4 temel kuralı uygular
    """

    @staticmethod
    def analyze_candles(prev_high: float, prev_low: float,
                       curr_high: float, curr_low: float) -> FractalPattern:
        """
        İki mum arasındaki fraktal ilişkiyi tespit et

        Args:
            prev_high (H0): Önceki mumun en yüksek fiyatı
            prev_low (L0): Önceki mumun en düşük fiyatı
            curr_high (H1): Mevcut mumun en yüksek fiyatı
            curr_low (L1): Mevcut mumun en düşük fiyatı

        Returns:
            FractalPattern: Tespit edilen patern
        """
        H0, L0 = prev_high, prev_low
        H1, L1 = curr_high, curr_low

        # KURAL 1: İç Mum (Inside Bar) - Daralma
        # (H1 < H0) VE (L1 > L0)
        if H1 < H0 and L1 > L0:
            return FractalPattern.INSIDE_BAR

        # KURAL 2: Dış Mum (Outside Bar) - Genişleme
        # (H1 > H0) VE (L1 < L0)
        elif H1 > H0 and L1 < L0:
            return FractalPattern.OUTSIDE_BAR

        # KURAL 3: Yükselen Yapı (Trending Up)
        # (H1 > H0) VE (L1 > L0)
        elif H1 > H0 and L1 > L0:
            return FractalPattern.TRENDING_UP

        # KURAL 4: Alçalan Yapı (Trending Down)
        # (H1 < H0) VE (L1 < L0)
        elif H1 < H0 and L1 < L0:
            return FractalPattern.TRENDING_DOWN

        else:
            return FractalPattern.UNKNOWN

    @staticmethod
    def calculate_strength(prev_high: float, prev_low: float,
                          curr_high: float, curr_low: float) -> float:
        """
        Patern gücünü hesapla (0-100 arası)

        Returns:
            float: Patern gücü (0-100)
        """
        prev_range = prev_high - prev_low
        curr_range = curr_high - curr_low

        if prev_range == 0:
            return 0.0

        # Genişleme/daralma oranı
        expansion_ratio = (curr_range / prev_range) * 100

        # Fiyat hareketi oranı
        price_move = abs(curr_high - prev_high) + abs(curr_low - prev_low)
        move_ratio = (price_move / prev_range) * 50

        # Toplam güç
        strength = min(100, (expansion_ratio + move_ratio) / 2)

        return strength

    @staticmethod
    def analyze_series(df: pd.DataFrame) -> pd.DataFrame:
        """
        Tüm veri serisi için fraktal analiz yap

        Args:
            df: DataFrame with 'high' and 'low' columns

        Returns:
            DataFrame with fractal analysis columns
        """
        df = df.copy()

        # Fraktal patern ve güç
        patterns = []
        strengths = []

        for i in range(1, len(df)):
            prev_h = df.iloc[i-1]['high']
            prev_l = df.iloc[i-1]['low']
            curr_h = df.iloc[i]['high']
            curr_l = df.iloc[i]['low']

            pattern = FractalAnalyzer.analyze_candles(prev_h, prev_l, curr_h, curr_l)
            strength = FractalAnalyzer.calculate_strength(prev_h, prev_l, curr_h, curr_l)

            patterns.append(pattern.value)
            strengths.append(strength)

        # İlk satır için NaN
        df['fractal_pattern'] = [None] + patterns
        df['fractal_strength'] = [0.0] + strengths

        return df


class MultiTimeframeFractalAnalyzer:
    """
    Çoklu zaman dilimi fraktal analiz motoru
    Her timeframe için fraktal yapıyı analiz eder ve dinamik ağırlıklandırma yapar
    """

    def __init__(self, weights: Dict[str, float] = None):
        """
        Args:
            weights: Her patern için ağırlıklar
                     Örn: {'TRENDING_UP': 2.0, 'INSIDE_BAR': 0.5}
        """
        self.default_weights = {
            'INSIDE_BAR': 0.5,      # Düşük güvenilirlik (kararsızlık)
            'OUTSIDE_BAR': 1.5,     # Orta-yüksek güvenilirlik (momentum)
            'TRENDING_UP': 2.0,     # Yüksek güvenilirlik (trend)
            'TRENDING_DOWN': 2.0    # Yüksek güvenilirlik (trend)
        }

        self.weights = weights if weights else self.default_weights

    def calculate_fractal_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fraktal skorunu hesapla (ağırlıklandırılmış)

        Returns:
            DataFrame with fractal_score column
        """
        df = df.copy()

        # Her patern için ağırlıklı skor
        def get_score(pattern, strength):
            if pd.isna(pattern):
                return 0.0

            weight = self.weights.get(pattern, 1.0)
            base_score = strength * weight

            # Trend paterni için bonus
            if 'Trending' in pattern:
                base_score *= 1.2

            return base_score

        df['fractal_score'] = df.apply(
            lambda row: get_score(row.get('fractal_pattern'), row.get('fractal_strength', 0)),
            axis=1
        )

        return df

    def get_signal_strength(self, df: pd.DataFrame, lookback: int = 5) -> pd.Series:
        """
        Son N mumun toplam sinyal gücünü hesapla

        Args:
            df: DataFrame with fractal analysis
            lookback: Kaç mum geriye bakılacak

        Returns:
            Series: Toplam sinyal gücü
        """
        return df['fractal_score'].rolling(window=lookback).mean()
