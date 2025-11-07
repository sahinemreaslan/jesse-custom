"""
Trading Routes Configuration
"""
from jesse.enums import timeframes

# Backtest routes
# Format: (exchange, symbol, timeframe, strategy_name)
routes = [
    # Fractal Cascade Strategy - Multi-timeframe fraktal yapı stratejisi
    # Piyasanın kalbi: Her timeframe'deki high-low ilişkisi fraktal bir yapı oluşturur
    ('Binance Futures', 'BTC-USDT', timeframes.MINUTE_15, 'FractalCascadeStrategy'),

    # GA Optimized Strategy (alternatif - Dual MA + RSI)
    # ('Binance Futures', 'BTC-USDT', timeframes.MINUTE_15, 'GAOptimizedStrategy'),
]

# Extra candles for multi-timeframe analysis
# FractalCascadeStrategy için gerekli (cascade analizi için)
extra_candles = [
    ('Binance Futures', 'BTC-USDT', timeframes.HOUR_1),   # 1h fraktal analiz
    ('Binance Futures', 'BTC-USDT', timeframes.HOUR_4),   # 4h fraktal analiz
]
