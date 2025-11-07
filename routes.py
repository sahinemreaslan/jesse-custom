"""
Trading Routes Configuration
"""
from jesse.enums import timeframes

# Backtest routes
# Format: (exchange, symbol, timeframe, strategy_name)
routes = [
    # Baseline strategy (Validated: 36.88% ROI, 22 months)
    # ('Binance Futures', 'BTC-USDT', timeframes.MINUTE_15, 'FractalTrend10x'),

    # Adaptive strategy (VALIDATED: 45.65% ROI, 22 months) ✅
    ('Binance Futures', 'BTC-USDT', timeframes.MINUTE_15, 'FractalTrendAdaptive'),
]

# Extra candles for multi-timeframe analysis
# Required for 4h EMA trend filter
extra_candles = [
    ('Binance Futures', 'BTC-USDT', timeframes.HOUR_4),
]
