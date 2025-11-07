"""
Fractal Trend HIGH QUALITY Strategy
====================================

Goal: Reduce trade count by 60-70% while maintaining or improving ROI

Filters:
1. Strong fractals only (strength >= 60)
2. Strong trends only (4h close >2% above EMA50)
3. High ADX (>25 for trending markets)
4. Volume confirmation (>1.2x average)
5. Fractal consistency check
6. Multiple timeframe alignment

Expected:
- Trades: ~1,800 (vs 5,800 baseline) - 69% reduction
- Win Rate: 55-60% (vs 49.7% baseline)
- ROI per trade: 2-3x higher
- Total ROI: Similar or better with less risk
"""

from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils
import numpy as np


class FractalTrendHighQuality(Strategy):
    """
    High quality trades only - strict filtering
    """

    def __init__(self):
        super().__init__()

        # Base parameters
        self.leverage = 10
        self.base_position_size = 0.05

        # Base exit parameters
        self.base_tp = 0.007
        self.base_sl = 0.0035

        # Trailing
        self.trailing_activation = 0.005
        self.trailing_distance = 0.002

        # === HIGH QUALITY FILTERS ===

        # Fractal filters (STRICTER)
        self.min_fractal_strength = 60  # Was 50, now 60
        self.min_fractal_consistency = 0.5  # New: require clean fractals

        # Trend filters (MUCH STRICTER)
        self.min_4h_trend_strength = 0.02  # Price must be >2% above EMA50
        self.min_4h_ema_slope = 0.0005  # EMA must be rising

        # ADX filter (STRICT)
        self.min_adx = 25  # Only trending markets

        # Volume filter (NEW)
        self.min_volume_ratio = 1.2  # Volume must be >1.2x average

        # Volatility adaptation
        self.atr_lookback = 100
        self.use_adaptive_tp_sl = True

        # Drawdown protection
        self.max_drawdown_for_sizing = -0.05
        self.use_drawdown_protection = True

        # Performance tracking
        self.recent_trades_window = 20
        self.recent_trade_results = []
        self.use_performance_adaptation = True

        # Market regime
        self.use_regime_detection = True

        # State
        self.entry_price = None
        self.highest_price = None
        self.trailing_active = False
        self.peak_balance = self.capital

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
        """15m ADX(14)"""
        return ta.adx(self.candles, period=14)

    @property
    def volume_15m(self):
        """15m volume"""
        return self.candles[:, 5]

    def baseline_atr(self):
        """Baseline ATR for volatility ratio"""
        if len(self.candles) < self.atr_lookback:
            return self.atr_15m

        atr_values = []
        for i in range(self.atr_lookback):
            idx = -(i + 1)
            atr_values.append(ta.atr(self.candles[:idx], period=14))

        return np.mean(atr_values)

    def get_4h_trend_strength(self):
        """
        Calculate 4h trend strength
        Returns: (close - ema50) / ema50
        """
        if len(self.close_4h) < 50:
            return 0

        current_close = self.close_4h[-1]
        current_ema = self.ema_4h[-1]

        if current_ema == 0:
            return 0

        return (current_close - current_ema) / current_ema

    def get_4h_ema_slope(self):
        """
        Calculate 4h EMA slope (is it rising?)
        Returns: (ema_now - ema_5_periods_ago) / ema_5_periods_ago
        """
        if len(self.ema_4h) < 6:
            return 0

        current_ema = self.ema_4h[-1]
        prev_ema = self.ema_4h[-6]  # 5 periods ago (20 hours)

        if prev_ema == 0:
            return 0

        return (current_ema - prev_ema) / prev_ema

    def get_volume_ratio(self):
        """
        Calculate volume ratio vs 20-period average
        """
        if len(self.volume_15m) < 20:
            return 1.0

        current_volume = self.volume_15m[-1]
        avg_volume = np.mean(self.volume_15m[-20:])

        if avg_volume == 0:
            return 1.0

        return current_volume / avg_volume

    def fractal_pattern(self):
        """
        Detect fractal patterns with consistency check
        Returns: (pattern, strength, consistency)
        """
        if len(self.candles) < 5:
            return None, 0, 0

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

                # Consistency: how clean are the progressions
                close_consistency = min(
                    (curr_close - prev1_close) / curr_close,
                    (prev1_close - prev2_close) / prev1_close
                ) if curr_close > 0 and prev1_close > 0 else 0

                return 'Trending Up', strength, close_consistency

        # Outside Bar
        elif (curr_high > prev1_high and
              curr_low < prev1_low and
              curr_close > curr_open):

            body = abs(curr_close - curr_open)
            range_size = curr_high - curr_low

            if range_size > 0:
                strength = int((body / range_size) * 100)

                # Consistency for outside bar: body ratio
                consistency = (body / range_size) if range_size > 0 else 0

                return 'Outside Bar', strength, consistency

        return None, 0, 0

    # ========================================================================
    # ADAPTIVE FEATURES (Same as baseline)
    # ========================================================================

    def get_volatility_ratio(self):
        """Calculate volatility ratio"""
        current_atr = self.atr_15m
        baseline = self.baseline_atr()

        if baseline == 0:
            return 1.0

        return current_atr / baseline

    def get_adaptive_tp_sl(self):
        """Volatility-Adaptive TP/SL"""
        if not self.use_adaptive_tp_sl:
            return self.base_tp, self.base_sl

        vol_ratio = self.get_volatility_ratio()

        adaptive_tp = self.base_tp * vol_ratio
        adaptive_sl = self.base_sl * vol_ratio

        adaptive_tp = np.clip(adaptive_tp, 0.004, 0.015)
        adaptive_sl = np.clip(adaptive_sl, 0.002, 0.008)

        return adaptive_tp, adaptive_sl

    def get_current_drawdown(self):
        """Calculate current drawdown"""
        current_balance = self.capital
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

        if self.peak_balance == 0:
            return 0

        return (current_balance - self.peak_balance) / self.peak_balance

    def get_drawdown_adjusted_position_size(self):
        """Drawdown-Based Position Sizing"""
        if not self.use_drawdown_protection:
            return self.base_position_size

        dd = self.get_current_drawdown()

        if dd >= 0:
            multiplier = 1.0
        elif dd > -0.01:
            multiplier = 1.0
        elif dd > -0.02:
            multiplier = 0.9
        elif dd > -0.03:
            multiplier = 0.7
        elif dd > -0.04:
            multiplier = 0.5
        elif dd > -0.05:
            multiplier = 0.3
        else:
            return 0

        adjusted_size = self.base_position_size * multiplier

        return adjusted_size

    def get_win_rate(self):
        """Calculate recent win rate"""
        if len(self.recent_trade_results) == 0:
            return 0.5

        wins = sum([1 for result in self.recent_trade_results if result > 0])
        return wins / len(self.recent_trade_results)

    def get_performance_multiplier(self):
        """Performance-Based Adjustment"""
        if not self.use_performance_adaptation:
            return 1.0

        if len(self.recent_trade_results) < 10:
            return 1.0

        win_rate = self.get_win_rate()

        if win_rate > 0.6:
            return 1.1
        elif win_rate < 0.4:
            return 0.9
        else:
            return 1.0

    def detect_market_regime(self):
        """Market Regime Detection"""
        if not self.use_regime_detection:
            return 'UNKNOWN'

        adx = self.adx_15m

        if adx > 25:
            return 'TRENDING'
        elif adx < 20:
            return 'RANGING'
        else:
            return 'TRANSITIONING'

    def get_regime_adjusted_params(self):
        """Adjust parameters based on market regime"""
        regime = self.detect_market_regime()

        if regime == 'TRENDING':
            return {
                'tp_multiplier': 1.2,
                'fractal_strength_adjustment': 0,  # Keep strict in trending
            }
        elif regime == 'RANGING':
            return {
                'tp_multiplier': 0.8,
                'fractal_strength_adjustment': +10,  # Extra strict in ranging
            }
        else:
            return {
                'tp_multiplier': 1.0,
                'fractal_strength_adjustment': +5,
            }

    # ========================================================================
    # ENTRY LOGIC (HIGH QUALITY FILTERS)
    # ========================================================================

    def should_long(self) -> bool:
        """
        Entry conditions with HIGH QUALITY filtering
        """
        # Check drawdown stop
        if self.get_current_drawdown() < self.max_drawdown_for_sizing:
            return False

        # === FILTER 1: FRACTAL QUALITY ===
        pattern, strength, consistency = self.fractal_pattern()

        if pattern not in ['Trending Up', 'Outside Bar']:
            return False

        # Regime-adjusted fractal strength
        regime_params = self.get_regime_adjusted_params()
        adjusted_strength_threshold = self.min_fractal_strength + regime_params['fractal_strength_adjustment']

        if strength < adjusted_strength_threshold:
            return False

        # NEW: Fractal consistency check
        if consistency < self.min_fractal_consistency:
            return False

        # === FILTER 2: 4H TREND QUALITY ===
        if len(self.close_4h) < 50:
            return False

        # Basic trend filter (close > ema50)
        if self.close_4h[-1] <= self.ema_4h[-1]:
            return False

        # NEW: Trend strength filter (price >2% above EMA)
        trend_strength = self.get_4h_trend_strength()
        if trend_strength < self.min_4h_trend_strength:
            return False

        # NEW: EMA must be rising
        ema_slope = self.get_4h_ema_slope()
        if ema_slope < self.min_4h_ema_slope:
            return False

        # === FILTER 3: ADX (TRENDING MARKET) ===
        if self.adx_15m < self.min_adx:
            return False

        # === FILTER 4: VOLUME CONFIRMATION ===
        volume_ratio = self.get_volume_ratio()
        if volume_ratio < self.min_volume_ratio:
            return False

        # All filters passed!
        return True

    def should_short(self) -> bool:
        """No shorts"""
        return False

    def should_cancel_entry(self) -> bool:
        return True

    # ========================================================================
    # POSITION MANAGEMENT (Same as baseline adaptive)
    # ========================================================================

    def go_long(self):
        """Open long with adaptive sizing"""
        adaptive_tp, adaptive_sl = self.get_adaptive_tp_sl()

        regime_params = self.get_regime_adjusted_params()
        adaptive_tp *= regime_params['tp_multiplier']

        drawdown_adjusted_size = self.get_drawdown_adjusted_position_size()

        if drawdown_adjusted_size == 0:
            return

        perf_multiplier = self.get_performance_multiplier()

        final_position_size = drawdown_adjusted_size * perf_multiplier

        final_position_size = np.clip(final_position_size, 0.01, 0.08)

        position_value = self.available_margin * final_position_size * self.leverage

        qty = utils.size_to_qty(
            position_value,
            self.price,
            fee_rate=self.fee_rate
        )

        self.buy = qty, self.price

        self.entry_price = self.price
        self.highest_price = self.price
        self.trailing_active = False

        tp_price = self.price * (1 + adaptive_tp)
        sl_price = self.price * (1 - adaptive_sl)

        self.take_profit = qty, tp_price
        self.stop_loss = qty, sl_price

    def update_position(self):
        """Update with trailing stop"""
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
        """Track trade results"""
        if order.is_executed:
            trade_pnl = order.pnl

            self.recent_trade_results.append(trade_pnl)

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
            {'name': 'min_fractal_strength', 'type': int, 'min': 55, 'max': 70, 'default': 60},
            {'name': 'min_4h_trend_strength', 'type': float, 'min': 0.01, 'max': 0.05, 'default': 0.02},
            {'name': 'min_adx', 'type': int, 'min': 20, 'max': 35, 'default': 25},
            {'name': 'min_volume_ratio', 'type': float, 'min': 1.0, 'max': 2.0, 'default': 1.2},
        ]
