"""
Fractal Trend 10x Aggressive Strategy
======================================

Kazanan Strateji: 36.88% ROI (22 months), MaxDD: -2.95%

Entry Rules:
1. 15m Fractal signal (Trending Up or Outside Bar)
2. Fractal strength >= 50
3. 4h trend filter (Price > EMA50)

Exit Rules:
- TP: 0.7%
- SL: 0.35%
- Trailing: Activate at 0.5%, trail 0.2%

Risk:
- Leverage: 10x
- Position: 5% capital * 10x = 50% exposure
"""

from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils
import numpy as np


class FractalTrend10x(Strategy):
    """
    10x Leveraged Fractal + 4h Trend Filter Strategy

    Validated Performance:
    - 22 months backtest: 36.88% ROI
    - Win rate: 52.1%
    - Profit factor: 1.36
    - Max drawdown: -2.95%
    - 0 Liquidations
    - Monte Carlo worst case: +12.60%
    """

    def __init__(self):
        super().__init__()

        # Strategy parameters (validated in backtests)
        self.min_fractal_strength = 50
        self.leverage = 10
        self.position_size_pct = 0.05  # 5% * 10x = 50% exposure

        # Exit parameters
        self.tp_percent = 0.007   # 0.7%
        self.sl_percent = 0.0035  # 0.35%

        # Trailing stop
        self.trailing_activation = 0.005  # 0.5%
        self.trailing_distance = 0.002    # 0.2%

        # State tracking
        self.entry_price = None
        self.highest_price = None
        self.trailing_active = False

    # ========================================================================
    # INDICATORS
    # ========================================================================

    @property
    def ema_4h(self):
        """4h EMA(50) for trend filter"""
        return ta.ema(self.get_candles(self.exchange, self.symbol, '4h'), period=50)

    @property
    def close_4h(self):
        """4h close price"""
        return self.get_candles(self.exchange, self.symbol, '4h')[:, 2]

    @property
    def atr_15m(self):
        """15m ATR for position sizing adjustment"""
        return ta.atr(self.candles, period=14)

    def fractal_pattern(self):
        """
        Detect fractal patterns on 15m timeframe
        Returns: (pattern_name, strength)
        """
        if len(self.candles) < 5:
            return None, 0

        # Current and previous candles
        curr = self.candles[-1]
        prev1 = self.candles[-2]
        prev2 = self.candles[-3]

        curr_open = curr[1]
        curr_high = curr[3]
        curr_low = curr[4]
        curr_close = curr[2]

        prev1_close = prev1[2]
        prev1_high = prev1[3]
        prev1_low = prev1[4]

        prev2_close = prev2[2]
        prev2_high = prev2[3]

        # Pattern 1: Trending Up
        # 3 consecutive higher closes and higher highs
        if (curr_close > prev1_close > prev2_close and
            curr_high > prev1_high > prev2_high):

            body = abs(curr_close - curr_open)
            range_size = curr_high - curr_low

            if range_size > 0:
                strength = int((body / range_size) * 100)
                return 'Trending Up', strength

        # Pattern 2: Outside Bar (Bullish Engulfing)
        # Current bar engulfs previous bar
        elif (curr_high > prev1_high and
              curr_low < prev1_low and
              curr_close > curr_open):  # Bullish

            body = abs(curr_close - curr_open)
            range_size = curr_high - curr_low

            if range_size > 0:
                strength = int((body / range_size) * 100)
                return 'Outside Bar', strength

        return None, 0

    # ========================================================================
    # ENTRY LOGIC
    # ========================================================================

    def should_long(self) -> bool:
        """
        Entry conditions (3 rules):
        1. Fractal pattern (Trending Up or Outside Bar)
        2. Fractal strength >= 50
        3. 4h trend up (close > EMA50)
        """
        # Rule 1 & 2: Fractal pattern and strength
        pattern, strength = self.fractal_pattern()

        if pattern not in ['Trending Up', 'Outside Bar']:
            return False

        if strength < self.min_fractal_strength:
            return False

        # Rule 3: 4h trend filter
        if len(self.close_4h) < 50:
            return False  # Not enough data for EMA

        if self.close_4h[-1] <= self.ema_4h[-1]:
            return False  # Price below 4h EMA50

        return True

    def should_short(self) -> bool:
        """No short positions"""
        return False

    def should_cancel_entry(self) -> bool:
        """Cancel entry if conditions no longer met"""
        return True

    # ========================================================================
    # POSITION MANAGEMENT
    # ========================================================================

    def go_long(self):
        """
        Open long position with 10x leverage
        """
        # Calculate position size (5% of capital * 10x leverage)
        position_value = self.available_margin * self.position_size_pct * self.leverage

        qty = utils.size_to_qty(
            position_value,
            self.price,
            fee_rate=self.fee_rate
        )

        # Entry
        self.buy = qty, self.price

        # Set entry tracking
        self.entry_price = self.price
        self.highest_price = self.price
        self.trailing_active = False

        # Take profit (0.7%)
        tp_price = self.price * (1 + self.tp_percent)
        self.take_profit = qty, tp_price

        # Stop loss (0.35%)
        sl_price = self.price * (1 - self.sl_percent)
        self.stop_loss = qty, sl_price

    def update_position(self):
        """
        Update position with trailing stop logic
        """
        if not self.is_long:
            return

        current_price = self.price

        # Update highest price
        if current_price > self.highest_price:
            self.highest_price = current_price

        # Check trailing stop activation (0.5% profit)
        if not self.trailing_active:
            if current_price >= self.entry_price * (1 + self.trailing_activation):
                self.trailing_active = True

        # Update trailing stop if active
        if self.trailing_active:
            trailing_stop_price = self.highest_price * (1 - self.trailing_distance)

            # Move stop loss to trailing stop if it's higher
            if trailing_stop_price > self.stop_loss[1]:
                self.stop_loss = self.position.qty, trailing_stop_price

    def go_short(self):
        """No short positions"""
        pass

    def filters(self) -> list:
        """
        Position filters
        """
        return [
            # Minimum 4h candles for EMA calculation
            self.get_candles(self.exchange, self.symbol, '4h').shape[0] >= 50,
        ]

    # ========================================================================
    # HYPERPARAMETERS (for optimization if needed)
    # ========================================================================

    def hyperparameters(self):
        """
        Hyperparameters for walk-forward optimization
        """
        return [
            {'name': 'min_fractal_strength', 'type': int, 'min': 40, 'max': 60, 'default': 50},
            {'name': 'position_size_pct', 'type': float, 'min': 0.03, 'max': 0.07, 'default': 0.05},
            {'name': 'tp_percent', 'type': float, 'min': 0.005, 'max': 0.010, 'default': 0.007},
            {'name': 'sl_percent', 'type': float, 'min': 0.0025, 'max': 0.0050, 'default': 0.0035},
        ]
