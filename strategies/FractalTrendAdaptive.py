"""
Fractal Trend ADAPTIVE Strategy
===============================

Baseline + Dinamik Özellikler:
1. Volatility-adaptive TP/SL (ATR-based)
2. Drawdown-based position sizing
3. Performance-based adjustments
4. Market regime detection (Trend/Range)

Evolution Plan: Bölüm 2 - Dinamik Yaklaşım
Timeline: Kısa vade (3-6 ay)

Expected Improvement: 40-50% ROI (vs 36.88% baseline)
"""

from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils
import numpy as np


class FractalTrendAdaptive(Strategy):
    """
    Adaptive version of winning strategy with dynamic features

    NEW FEATURES:
    1. ATR-based dynamic TP/SL (volatility adaptation)
    2. Drawdown-based position sizing (risk management)
    3. Win streak bonuses (performance adaptation)
    4. ADX-based regime detection (trend/range awareness)
    """

    def __init__(self):
        super().__init__()

        # Base parameters (from baseline)
        self.min_fractal_strength = 50
        self.leverage = 10
        self.base_position_size = 0.05  # 5%

        # Base exit parameters
        self.base_tp = 0.007   # 0.7%
        self.base_sl = 0.0035  # 0.35%

        # Trailing
        self.trailing_activation = 0.005
        self.trailing_distance = 0.002

        # === DYNAMIC FEATURES ===

        # Volatility adaptation
        self.atr_lookback = 100  # ATR baseline period
        self.use_adaptive_tp_sl = True

        # Drawdown protection
        self.max_drawdown_for_sizing = -0.05  # Stop at -5%
        self.use_drawdown_protection = True

        # Performance tracking
        self.recent_trades_window = 20
        self.recent_trade_results = []  # Track last N trades
        self.use_performance_adaptation = True

        # Market regime
        self.use_regime_detection = True
        self.adx_trending_threshold = 25
        self.adx_ranging_threshold = 20

        # State
        self.entry_price = None
        self.highest_price = None
        self.trailing_active = False
        self.peak_balance = self.capital  # Track for drawdown

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
        """15m ATR(14)"""
        return ta.atr(self.candles, period=14)

    @property
    def adx_15m(self):
        """15m ADX(14) for regime detection"""
        return ta.adx(self.candles, period=14)

    def baseline_atr(self):
        """
        Baseline ATR (100-period average)
        Used for volatility ratio calculation
        """
        if len(self.candles) < self.atr_lookback:
            return self.atr_15m

        atr_values = []
        for i in range(self.atr_lookback):
            idx = -(i + 1)
            atr_values.append(ta.atr(self.candles[:idx], period=14))

        return np.mean(atr_values)

    def fractal_pattern(self):
        """Detect fractal patterns (same as baseline)"""
        if len(self.candles) < 5:
            return None, 0

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

        # Trending Up
        if (curr_close > prev1_close > prev2_close and
            curr_high > prev1_high > prev2_high):

            body = abs(curr_close - curr_open)
            range_size = curr_high - curr_low

            if range_size > 0:
                strength = int((body / range_size) * 100)
                return 'Trending Up', strength

        # Outside Bar
        elif (curr_high > prev1_high and
              curr_low < prev1_low and
              curr_close > curr_open):

            body = abs(curr_close - curr_open)
            range_size = curr_high - curr_low

            if range_size > 0:
                strength = int((body / range_size) * 100)
                return 'Outside Bar', strength

        return None, 0

    # ========================================================================
    # DYNAMIC FEATURES
    # ========================================================================

    def get_volatility_ratio(self):
        """
        Calculate volatility ratio
        ratio > 1: High volatility
        ratio < 1: Low volatility
        """
        current_atr = self.atr_15m
        baseline = self.baseline_atr()

        if baseline == 0:
            return 1.0

        return current_atr / baseline

    def get_adaptive_tp_sl(self):
        """
        FEATURE 1: Volatility-Adaptive TP/SL

        High volatility → Wider TP/SL
        Low volatility → Tighter TP/SL
        """
        if not self.use_adaptive_tp_sl:
            return self.base_tp, self.base_sl

        vol_ratio = self.get_volatility_ratio()

        # Apply volatility scaling
        adaptive_tp = self.base_tp * vol_ratio
        adaptive_sl = self.base_sl * vol_ratio

        # Clamp to reasonable bounds
        adaptive_tp = np.clip(adaptive_tp, 0.004, 0.015)  # 0.4% - 1.5%
        adaptive_sl = np.clip(adaptive_sl, 0.002, 0.008)  # 0.2% - 0.8%

        return adaptive_tp, adaptive_sl

    def get_current_drawdown(self):
        """
        Calculate current drawdown
        """
        current_balance = self.capital
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

        if self.peak_balance == 0:
            return 0

        return (current_balance - self.peak_balance) / self.peak_balance

    def get_drawdown_adjusted_position_size(self):
        """
        FEATURE 2: Drawdown-Based Position Sizing

        As drawdown increases, reduce position size
        """
        if not self.use_drawdown_protection:
            return self.base_position_size

        dd = self.get_current_drawdown()

        # Position size adjustment based on drawdown
        if dd >= 0:
            # No drawdown or new peak
            multiplier = 1.0
        elif dd > -0.01:  # 0 to -1%
            multiplier = 1.0
        elif dd > -0.02:  # -1% to -2%
            multiplier = 0.9
        elif dd > -0.03:  # -2% to -3%
            multiplier = 0.7
        elif dd > -0.04:  # -3% to -4%
            multiplier = 0.5
        elif dd > -0.05:  # -4% to -5%
            multiplier = 0.3
        else:  # > -5%
            # Stop trading completely
            return 0

        adjusted_size = self.base_position_size * multiplier

        return adjusted_size

    def get_win_rate(self):
        """Calculate recent win rate"""
        if len(self.recent_trade_results) == 0:
            return 0.5  # Neutral

        wins = sum([1 for result in self.recent_trade_results if result > 0])
        return wins / len(self.recent_trade_results)

    def get_performance_multiplier(self):
        """
        FEATURE 3: Performance-Based Adjustment

        Hot streak (win rate > 60%) → Increase position slightly
        Cold streak (win rate < 40%) → Decrease position
        """
        if not self.use_performance_adaptation:
            return 1.0

        if len(self.recent_trade_results) < 10:
            return 1.0  # Not enough data

        win_rate = self.get_win_rate()

        if win_rate > 0.6:  # Hot streak
            return 1.1  # +10%
        elif win_rate < 0.4:  # Cold streak
            return 0.9  # -10%
        else:
            return 1.0

    def detect_market_regime(self):
        """
        FEATURE 4: Market Regime Detection

        Returns: 'TRENDING', 'RANGING', 'TRANSITIONING'
        """
        if not self.use_regime_detection:
            return 'UNKNOWN'

        adx = self.adx_15m

        if adx > self.adx_trending_threshold:
            return 'TRENDING'
        elif adx < self.adx_ranging_threshold:
            return 'RANGING'
        else:
            return 'TRANSITIONING'

    def get_regime_adjusted_params(self):
        """
        Adjust parameters based on market regime

        TRENDING: Longer TP, less strict fractal
        RANGING: Shorter TP, more strict fractal
        """
        regime = self.detect_market_regime()

        if regime == 'TRENDING':
            return {
                'tp_multiplier': 1.2,  # Longer TP
                'fractal_strength_adjustment': -5,  # Less strict
            }
        elif regime == 'RANGING':
            return {
                'tp_multiplier': 0.8,  # Shorter TP
                'fractal_strength_adjustment': +10,  # More strict
            }
        else:
            return {
                'tp_multiplier': 1.0,
                'fractal_strength_adjustment': 0,
            }

    # ========================================================================
    # ENTRY LOGIC (Enhanced with adaptive features)
    # ========================================================================

    def should_long(self) -> bool:
        """
        Entry conditions with adaptive filtering
        """
        # Check drawdown stop
        if self.get_current_drawdown() < self.max_drawdown_for_sizing:
            return False  # Stop trading

        # Regime-adjusted fractal strength
        regime_params = self.get_regime_adjusted_params()
        adjusted_strength_threshold = self.min_fractal_strength + regime_params['fractal_strength_adjustment']

        # Fractal pattern
        pattern, strength = self.fractal_pattern()

        if pattern not in ['Trending Up', 'Outside Bar']:
            return False

        if strength < adjusted_strength_threshold:
            return False

        # 4h trend filter
        if len(self.close_4h) < 50:
            return False

        if self.close_4h[-1] <= self.ema_4h[-1]:
            return False

        return True

    def should_short(self) -> bool:
        """No shorts"""
        return False

    def should_cancel_entry(self) -> bool:
        return True

    # ========================================================================
    # POSITION MANAGEMENT (With adaptive sizing)
    # ========================================================================

    def go_long(self):
        """
        Open long with ADAPTIVE position sizing
        """
        # Get adaptive TP/SL
        adaptive_tp, adaptive_sl = self.get_adaptive_tp_sl()

        # Get regime adjustments
        regime_params = self.get_regime_adjusted_params()
        adaptive_tp *= regime_params['tp_multiplier']

        # Get drawdown-adjusted position size
        drawdown_adjusted_size = self.get_drawdown_adjusted_position_size()

        if drawdown_adjusted_size == 0:
            return  # Don't trade

        # Get performance multiplier
        perf_multiplier = self.get_performance_multiplier()

        # Final position size
        final_position_size = drawdown_adjusted_size * perf_multiplier

        # Clamp
        final_position_size = np.clip(final_position_size, 0.01, 0.08)

        # Calculate quantity
        position_value = self.available_margin * final_position_size * self.leverage

        qty = utils.size_to_qty(
            position_value,
            self.price,
            fee_rate=self.fee_rate
        )

        # Entry
        self.buy = qty, self.price

        # Track state
        self.entry_price = self.price
        self.highest_price = self.price
        self.trailing_active = False

        # Adaptive TP/SL
        tp_price = self.price * (1 + adaptive_tp)
        sl_price = self.price * (1 - adaptive_sl)

        self.take_profit = qty, tp_price
        self.stop_loss = qty, sl_price

    def update_position(self):
        """
        Update with trailing stop (same as baseline)
        """
        if not self.is_long:
            return

        current_price = self.price

        if current_price > self.highest_price:
            self.highest_price = current_price

        if not self.trailing_active:
            if current_price >= self.entry_price * (1 + self.trailing_activation):
                self.trailing_active = True

        if self.trailing_active:
            trailing_stop_price = self.highest_price * (1 - self.trailing_distance)

            if trailing_stop_price > self.stop_loss[1]:
                self.stop_loss = self.position.qty, trailing_stop_price

    def on_close_position(self, order):
        """
        Track trade results for performance adaptation
        """
        # Calculate PnL
        if order.is_executed:
            trade_pnl = order.pnl

            # Store result
            self.recent_trade_results.append(trade_pnl)

            # Keep only recent window
            if len(self.recent_trade_results) > self.recent_trades_window:
                self.recent_trade_results.pop(0)

    def go_short(self):
        pass

    def filters(self) -> list:
        return [
            self.get_candles(self.exchange, self.symbol, '4h').shape[0] >= 50,
        ]

    def hyperparameters(self):
        return [
            {'name': 'min_fractal_strength', 'type': int, 'min': 40, 'max': 60, 'default': 50},
            {'name': 'base_position_size', 'type': float, 'min': 0.03, 'max': 0.07, 'default': 0.05},
            {'name': 'base_tp', 'type': float, 'min': 0.005, 'max': 0.010, 'default': 0.007},
            {'name': 'base_sl', 'type': float, 'min': 0.0025, 'max': 0.0050, 'default': 0.0035},

            # Adaptive feature toggles
            {'name': 'use_adaptive_tp_sl', 'type': bool, 'default': True},
            {'name': 'use_drawdown_protection', 'type': bool, 'default': True},
            {'name': 'use_performance_adaptation', 'type': bool, 'default': True},
            {'name': 'use_regime_detection', 'type': bool, 'default': True},
        ]
