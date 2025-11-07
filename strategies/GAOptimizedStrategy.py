"""
GA Optimized Strategy - Genetik Algoritma ile Optimize Edilebilir Strateji

Bu strateji Jesse'nin Strategy base class'ını kullanır ve
Genetik Algoritma tarafından parametreleri optimize edilir.

Strateji: Dual MA + RSI + Trend Filter
"""

import os
import json
from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils


class GAOptimizedStrategy(Strategy):
    """
    Genetik Algoritma ile optimize edilebilir örnek strateji.

    Parametre Optimizasyonu:
    - fast_ma: Hızlı hareketli ortalama periyodu
    - slow_ma: Yavaş hareketli ortalama periyodu
    - rsi_period: RSI periyodu
    - rsi_buy_threshold: RSI alım eşiği
    - rsi_sell_threshold: RSI satım eşiği
    - use_trend_filter: Trend filtresi kullan
    """

    def __init__(self):
        super().__init__()

        # Parametreleri environment variable'dan veya default'tan al
        self.params = self._load_parameters()

    def _load_parameters(self) -> dict:
        """
        Parametreleri yükle.

        Öncelik:
        1. Environment variable (GA_PARAMS)
        2. Hyperparameters() method
        3. Default değerler
        """
        # Environment variable kontrolü (GA optimizer tarafından set edilir)
        env_params = os.environ.get('GA_PARAMS')
        if env_params:
            try:
                return json.loads(env_params)
            except:
                pass

        # Default parametreler
        return {
            'fast_ma': 20,
            'slow_ma': 50,
            'rsi_period': 14,
            'rsi_buy_threshold': 30,
            'rsi_sell_threshold': 70,
            'use_trend_filter': True,
        }

    @property
    def fast_ma(self):
        return self.params.get('fast_ma', 20)

    @property
    def slow_ma(self):
        return self.params.get('slow_ma', 50)

    @property
    def rsi_period(self):
        return self.params.get('rsi_period', 14)

    @property
    def rsi_buy_threshold(self):
        return self.params.get('rsi_buy_threshold', 30)

    @property
    def rsi_sell_threshold(self):
        return self.params.get('rsi_sell_threshold', 70)

    @property
    def use_trend_filter(self):
        return self.params.get('use_trend_filter', True)

    def should_long(self) -> bool:
        """Long pozisyon açma sinyali."""
        # İndikatörleri hesapla
        fast_ma_val = ta.ema(self.candles, self.fast_ma)
        slow_ma_val = ta.ema(self.candles, self.slow_ma)
        rsi_val = ta.rsi(self.candles, self.rsi_period)

        # MA crossover
        ma_cross = fast_ma_val[-1] > slow_ma_val[-1] and fast_ma_val[-2] <= slow_ma_val[-2]

        # RSI oversold
        rsi_oversold = rsi_val <= self.rsi_buy_threshold

        # Trend filter (200 EMA)
        if self.use_trend_filter:
            trend_ema = ta.ema(self.candles, 200)
            trend_up = self.close > trend_ema
            return ma_cross and rsi_oversold and trend_up
        else:
            return ma_cross and rsi_oversold

    def should_short(self) -> bool:
        """Short pozisyon açma sinyali."""
        # İndikatörleri hesapla
        fast_ma_val = ta.ema(self.candles, self.fast_ma)
        slow_ma_val = ta.ema(self.candles, self.slow_ma)
        rsi_val = ta.rsi(self.candles, self.rsi_period)

        # MA crossover
        ma_cross = fast_ma_val[-1] < slow_ma_val[-1] and fast_ma_val[-2] >= slow_ma_val[-2]

        # RSI overbought
        rsi_overbought = rsi_val >= self.rsi_sell_threshold

        # Trend filter
        if self.use_trend_filter:
            trend_ema = ta.ema(self.candles, 200)
            trend_down = self.close < trend_ema
            return ma_cross and rsi_overbought and trend_down
        else:
            return ma_cross and rsi_overbought

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
        # Basit trailing stop
        if self.is_long:
            # Long için stop
            stop_price = self.price * 0.98  # %2 stop loss
            if self.price < stop_price:
                self.liquidate()

        elif self.is_short:
            # Short için stop
            stop_price = self.price * 1.02  # %2 stop loss
            if self.price > stop_price:
                self.liquidate()

    # Hyperparameters tanımı (Jesse optimizer için)
    @staticmethod
    def hyperparameters():
        """
        Jesse'nin built-in optimizer'ı için hyperparameter tanımı.

        GA optimizer bu değerleri kullanmaz, kendi ParameterSpace'ini kullanır.
        """
        return [
            {'name': 'fast_ma', 'type': int, 'min': 5, 'max': 50, 'default': 20},
            {'name': 'slow_ma', 'type': int, 'min': 50, 'max': 200, 'default': 50},
            {'name': 'rsi_period', 'type': int, 'min': 7, 'max': 28, 'default': 14},
            {'name': 'rsi_buy_threshold', 'type': int, 'min': 20, 'max': 40, 'default': 30},
            {'name': 'rsi_sell_threshold', 'type': int, 'min': 60, 'max': 80, 'default': 70},
            {'name': 'use_trend_filter', 'type': bool, 'default': True},
        ]
