"""
Fractal Cascade Strategy - Multi-Timeframe Fraktal Yapı Stratejisi

Piyasanın kalbi: Her zaman dilimindeki high-low ilişkisi fraktal bir yapı oluşturur.

Strateji Mantığı:
1. Her timeframe'de (15m, 1h, 4h) fraktal pattern tespit et
2. Pattern'leri cascade analizi ile birleştir
3. Dominant pattern ve cascade strength'e göre karar ver
4. Yüksek confidence'ta pozisyon aç

Fraktal Pattern'ler:
- Inside Bar (H1 < H0 AND L1 > L0): Daralma, konsolidasyon
- Outside Bar (H1 > H0 AND L1 < L0): Genişleme, momentum değişimi
- Trending Up (H1 > H0 AND L1 > L0): Yükseliş momentumu
- Trending Down (H1 < H0 AND L1 < L0): Düşüş momentumu
"""

import os
import json
import sys
from pathlib import Path

# Fractal cascade'i import et
sys.path.insert(0, str(Path(__file__).parent.parent))
from ga_optimizer.utils.fractal_cascade import (
    FractalCascade,
    FractalCascadeLevel,
    FractalPattern
)
from fractal_analyzer import FractalAnalyzer

from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils


class FractalCascadeStrategy(Strategy):
    """
    Multi-timeframe fraktal cascade stratejisi.

    GA Optimize Edilebilir Parametreler:
    - cascade_threshold: Minimum cascade score
    - min_confidence: Minimum güven seviyesi
    - use_rsi_filter: RSI filtresi kullan
    - rsi_period: RSI periyodu
    - rsi_buy: RSI alım eşiği
    - rsi_sell: RSI satım eşiği
    """

    def __init__(self):
        super().__init__()

        # Parametreleri yükle
        self.params = self._load_parameters()

    def _load_parameters(self) -> dict:
        """Parametreleri environment variable veya default'tan al."""
        env_params = os.environ.get('GA_PARAMS')
        if env_params:
            try:
                return json.loads(env_params)
            except:
                pass

        return {
            'cascade_threshold': 3.0,     # Minimum cascade score
            'min_confidence': 0.5,        # Min %50 güven
            'use_rsi_filter': True,       # RSI filtresi
            'rsi_period': 14,
            'rsi_buy': 30,
            'rsi_sell': 70,
            'use_volume_filter': False,   # Hacim filtresi
            'volume_multiplier': 1.2,     # Min 1.2x ortalama hacim
        }

    @property
    def cascade_threshold(self):
        return self.params.get('cascade_threshold', 3.0)

    @property
    def min_confidence(self):
        return self.params.get('min_confidence', 0.5)

    @property
    def use_rsi_filter(self):
        return self.params.get('use_rsi_filter', True)

    @property
    def rsi_period(self):
        return self.params.get('rsi_period', 14)

    @property
    def rsi_buy(self):
        return self.params.get('rsi_buy', 30)

    @property
    def rsi_sell(self):
        return self.params.get('rsi_sell', 70)

    @property
    def use_volume_filter(self):
        return self.params.get('use_volume_filter', False)

    @property
    def volume_multiplier(self):
        return self.params.get('volume_multiplier', 1.2)

    def _get_cascade_analysis(self) -> dict:
        """Multi-timeframe cascade analizi yap."""
        import pandas as pd

        # Mevcut timeframe (15m)
        df_15m = pd.DataFrame({
            'high': self.candles[:, 3],
            'low': self.candles[:, 4],
            'close': self.candles[:, 2],
            'volume': self.candles[:, 5],
        })

        # 1h candles (extra candles olarak eklenmeli)
        try:
            df_1h = pd.DataFrame({
                'high': self.get_candles(self.exchange, self.symbol, '1h')[:, 3],
                'low': self.get_candles(self.exchange, self.symbol, '1h')[:, 4],
                'close': self.get_candles(self.exchange, self.symbol, '1h')[:, 2],
            })
        except:
            df_1h = None

        # 4h candles
        try:
            df_4h = pd.DataFrame({
                'high': self.get_candles(self.exchange, self.symbol, '4h')[:, 3],
                'low': self.get_candles(self.exchange, self.symbol, '4h')[:, 4],
                'close': self.get_candles(self.exchange, self.symbol, '4h')[:, 2],
            })
        except:
            df_4h = None

        # Cascade data oluştur
        timeframe_data = {
            FractalCascadeLevel.SHORT: df_15m,
        }

        if df_1h is not None:
            timeframe_data[FractalCascadeLevel.MEDIUM] = df_1h

        if df_4h is not None:
            timeframe_data[FractalCascadeLevel.LONG] = df_4h

        # Cascade analizi
        cascade_result = FractalCascade.analyze_cascade(timeframe_data)

        return cascade_result

    def should_long(self) -> bool:
        """Long pozisyon açma sinyali."""
        # Cascade analizi
        cascade = self._get_cascade_analysis()

        # Sinyal al
        signal, explanation = FractalCascade.get_cascade_signal(
            cascade,
            threshold=self.cascade_threshold
        )

        # Confidence kontrolü
        confidence = FractalCascade.get_cascade_confidence(cascade)

        if signal != 1:  # LONG değilse
            return False

        if confidence < self.min_confidence:
            return False

        # RSI filtresi
        if self.use_rsi_filter:
            rsi_val = ta.rsi(self.candles, self.rsi_period)
            if rsi_val > self.rsi_buy:  # Çok yükseğe gelmiş
                return False

        # Volume filtresi
        if self.use_volume_filter:
            avg_volume = ta.sma(self.candles[:, 5], 20)
            current_volume = self.candles[-1, 5]
            if current_volume < avg_volume * self.volume_multiplier:
                return False

        return True

    def should_short(self) -> bool:
        """Short pozisyon açma sinyali."""
        # Cascade analizi
        cascade = self._get_cascade_analysis()

        # Sinyal al
        signal, explanation = FractalCascade.get_cascade_signal(
            cascade,
            threshold=self.cascade_threshold
        )

        # Confidence kontrolü
        confidence = FractalCascade.get_cascade_confidence(cascade)

        if signal != -1:  # SHORT değilse
            return False

        if confidence < self.min_confidence:
            return False

        # RSI filtresi
        if self.use_rsi_filter:
            rsi_val = ta.rsi(self.candles, self.rsi_period)
            if rsi_val < self.rsi_sell:  # Çok düşüğe gelmiş
                return False

        # Volume filtresi
        if self.use_volume_filter:
            avg_volume = ta.sma(self.candles[:, 5], 20)
            current_volume = self.candles[-1, 5]
            if current_volume < avg_volume * self.volume_multiplier:
                return False

        return True

    def should_cancel_entry(self) -> bool:
        """Entry emrini iptal et."""
        return False

    def go_long(self):
        """Long pozisyon aç."""
        qty = utils.size_to_qty(
            self.balance * 0.95,  # %95 kullan
            self.price
        )

        self.buy = qty, self.price

    def go_short(self):
        """Short pozisyon aç."""
        qty = utils.size_to_qty(
            self.balance * 0.95,
            self.price
        )

        self.sell = qty, self.price

    def update_position(self):
        """Açık pozisyonu güncelle."""
        # ATR-based trailing stop
        atr = ta.atr(self.candles, 14)
        stop_distance = atr * 2.0  # 2x ATR stop

        if self.is_long:
            stop_price = self.price - stop_distance
            if self.price < stop_price:
                self.liquidate()

        elif self.is_short:
            stop_price = self.price + stop_distance
            if self.price > stop_price:
                self.liquidate()

    @staticmethod
    def hyperparameters():
        """GA optimizer için hyperparameter tanımı."""
        return [
            {'name': 'cascade_threshold', 'type': float, 'min': 1.0, 'max': 10.0, 'default': 3.0},
            {'name': 'min_confidence', 'type': float, 'min': 0.3, 'max': 0.9, 'default': 0.5},
            {'name': 'use_rsi_filter', 'type': bool, 'default': True},
            {'name': 'rsi_period', 'type': int, 'min': 7, 'max': 28, 'default': 14},
            {'name': 'rsi_buy', 'type': int, 'min': 20, 'max': 40, 'default': 30},
            {'name': 'rsi_sell', 'type': int, 'min': 60, 'max': 80, 'default': 70},
            {'name': 'use_volume_filter', 'type': bool, 'default': False},
            {'name': 'volume_multiplier', 'type': float, 'min': 1.0, 'max': 2.0, 'default': 1.2},
        ]
