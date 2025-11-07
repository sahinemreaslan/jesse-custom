"""
Trading Routes Configuration
"""
from jesse.enums import timeframes

# Backtest routes
# Format: (exchange, symbol, timeframe, strategy_name)
routes = [
    # GA Optimized Strategy - Genetik Algoritma ile optimize edilen strateji
    ('Binance Futures', 'BTC-USDT', timeframes.MINUTE_15, 'GAOptimizedStrategy'),
]

# Extra candles for multi-timeframe analysis (opsiyonel)
extra_candles = [
    # ('Binance Futures', 'BTC-USDT', timeframes.HOUR_4),
]
