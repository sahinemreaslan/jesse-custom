"""
GA Trading System - Strategy Templates

Hazır strateji şablonları:
- DualMaRsiStrategy: Dual MA + RSI
- TripleEmaMacdStrategy: Triple EMA + MACD
- CustomStrategy: Özelleştirilebilir şablon
"""

from .dual_ma_rsi import DualMaRsiStrategy
from .triple_ema_macd import TripleEmaMacdStrategy
from .custom_strategy import CustomStrategy

__all__ = [
    'DualMaRsiStrategy',
    'TripleEmaMacdStrategy',
    'CustomStrategy',
]
