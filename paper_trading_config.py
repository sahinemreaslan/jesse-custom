"""
Paper Trading Configuration
============================

Two strategies ready for testing:
1. FractalTrend10x (Baseline - Validated 36.88% ROI)
2. FractalTrendAdaptive (Dynamic features)

Usage:
    # Test baseline
    jesse backtest 2024-01-01 2024-10-31

    # Compare adaptive
    jesse backtest 2024-01-01 2024-10-31 --strategy FractalTrendAdaptive
"""

# ========================================================================
# PAPER TRADING SETUP
# ========================================================================

PAPER_TRADING_CONFIG = {
    'exchange': 'Binance Futures',
    'symbol': 'BTC-USDT',
    'timeframe': '15m',
    'starting_balance': 10000,  # $10,000
    'fee': 0.0004,  # 0.04% (Binance Futures maker/taker)

    # Leverage
    'futures_leverage': 10,
    'futures_leverage_mode': 'cross',  # or 'isolated'

    # Strategy selection
    'strategy_name': 'FractalTrend10x',  # or 'FractalTrendAdaptive'

    # Warm-up period
    'warm_up_candles': 200,  # Need at least 50 for 4h EMA + 150 buffer
}

# ========================================================================
# BACKTEST PERIODS (for validation)
# ========================================================================

BACKTEST_PERIODS = {
    'short_term': {
        'start': '2024-10-01',
        'end': '2024-10-31',
        'description': 'Q4 2024 (1 month)'
    },
    'medium_term': {
        'start': '2024-01-01',
        'end': '2024-10-31',
        'description': '2024 (10 months)'
    },
    'long_term': {
        'start': '2023-01-01',
        'end': '2024-10-31',
        'description': '2023-2024 (22 months)'
    },
}

# ========================================================================
# ROUTE CONFIGURATION (Jesse routes.py format)
# ========================================================================

ROUTES = [
    {
        'exchange': 'Binance Futures',
        'symbol': 'BTC-USDT',
        'timeframe': '15m',
        'strategy': 'FractalTrend10x',  # Baseline
    },
]

# Extra candles (for multi-timeframe analysis)
EXTRA_CANDLES = [
    ('Binance Futures', 'BTC-USDT', '4h'),  # For trend filter
]

# ========================================================================
# MONITORING & ALERTS
# ========================================================================

MONITORING = {
    # Performance thresholds
    'alert_on_drawdown': -0.03,  # Alert if DD > 3%
    'stop_trading_drawdown': -0.05,  # Stop if DD > 5%

    # Position limits
    'max_open_positions': 1,  # One position at a time
    'max_daily_trades': 20,  # Prevent overtrading

    # Performance tracking
    'track_metrics': [
        'roi',
        'win_rate',
        'profit_factor',
        'max_drawdown',
        'sharpe_ratio',
        'total_trades',
    ],

    # Logging
    'log_level': 'INFO',
    'log_trades': True,
    'log_indicators': False,  # Set True for debugging
}

# ========================================================================
# PAPER TRADING vs LIVE TRADING
# ========================================================================

TRADING_MODES = {
    'paper': {
        'description': 'Paper trading (simulated)',
        'balance': 10000,
        'use_testnet': False,  # Use real data, simulated trading
        'duration': '1-2 months',
        'success_criteria': {
            'min_roi': 0.10,  # 10% minimum
            'min_trades': 50,  # At least 50 trades
            'max_drawdown': -0.05,  # Max -5% DD
            'consistency': 'Positive ROI in 3/4 weeks',
        }
    },
    'live_minimal': {
        'description': 'Live trading (small capital)',
        'balance': 1000,  # Start with $1000
        'use_testnet': False,
        'duration': '1-2 months',
        'success_criteria': {
            'min_roi': 0.15,  # 15% minimum
            'min_trades': 100,
            'max_drawdown': -0.05,
            'consistency': 'Beat paper trading performance',
        }
    },
    'live_full': {
        'description': 'Live trading (full capital)',
        'balance': 10000,
        'use_testnet': False,
        'duration': 'Ongoing',
        'success_criteria': {
            'min_roi': 0.20,  # 20% annually
            'sharpe_ratio': 1.5,
            'max_drawdown': -0.05,
        }
    }
}

# ========================================================================
# TRANSITION PLAN
# ========================================================================

TRANSITION_PLAN = """
Phase 1: Backtest Validation (Done ✅)
--------------------------------------
✅ 22-month backtest: 36.88% ROI
✅ Walk-forward validation
✅ Monte Carlo simulation
✅ 0 liquidations

Phase 2: Paper Trading (Current - 1-2 months)
---------------------------------------------
Week 1-2: FractalTrend10x (Baseline)
    - Monitor daily performance
    - Track vs backtest expectations
    - Debug any issues

Week 3-4: FractalTrendAdaptive (Dynamic)
    - Compare vs baseline
    - Analyze adaptive features impact
    - Tune parameters if needed

Success Criteria:
    - ROI >= 10% (2 months)
    - Max DD < 5%
    - 50+ trades
    - Win rate ~52%

Phase 3: Live Trading - Minimal Capital (1-2 months)
---------------------------------------------------
Start: $1,000 capital
Leverage: 5x (conservative start)

Week 1-4: Observe and monitor
    - Real slippage impact
    - Real commission impact
    - Execution quality

Week 5-8: Gradual increase
    - If performing well, increase to 10x leverage
    - Add capital if consistent

Success Criteria:
    - Beat paper trading ROI
    - Max DD < 5%
    - No major execution issues

Phase 4: Live Trading - Full Capital (Ongoing)
---------------------------------------------
Capital: $10,000+
Leverage: 10x
Strategy: Best performer (Baseline or Adaptive)

Ongoing Monitoring:
    - Daily performance review
    - Weekly drawdown check
    - Monthly strategy review
    - Quarterly optimization
"""

# ========================================================================
# RISK MANAGEMENT RULES
# ========================================================================

RISK_RULES = {
    'max_position_size': 0.50,  # 50% exposure max (5% * 10x)
    'max_leverage': 10,
    'max_daily_loss': -0.02,  # -2% daily stop
    'max_weekly_loss': -0.05,  # -5% weekly stop
    'max_drawdown': -0.05,  # -5% total DD stop

    'position_limits': {
        'min_qty': 0.001,  # Minimum BTC
        'max_qty': 0.1,    # Maximum BTC per trade
    },

    'emergency_stop': {
        'conditions': [
            'drawdown < -5%',
            'consecutive_losses >= 5',
            'daily_trades > 50',
            'liquidation_occurred',
        ],
        'action': 'STOP_ALL_TRADING',
    }
}

# ========================================================================
# COMPARISON METRICS
# ========================================================================

COMPARISON_METRICS = {
    'baseline_vs_adaptive': {
        'expected': {
            'baseline_roi': 0.22,  # 22% (10 months)
            'adaptive_roi': 0.28,  # 28% (expected +25% improvement)
            'baseline_dd': -0.0295,
            'adaptive_dd': -0.025,  # Expected lower DD
        },
        'track': [
            'roi_difference',
            'sharpe_ratio',
            'max_drawdown',
            'win_rate',
            'profit_factor',
            'avg_trade_duration',
            'trades_per_month',
        ]
    }
}

if __name__ == '__main__':
    print("=" * 80)
    print("PAPER TRADING CONFIGURATION")
    print("=" * 80)
    print()
    print(f"Exchange: {PAPER_TRADING_CONFIG['exchange']}")
    print(f"Symbol: {PAPER_TRADING_CONFIG['symbol']}")
    print(f"Timeframe: {PAPER_TRADING_CONFIG['timeframe']}")
    print(f"Starting Balance: ${PAPER_TRADING_CONFIG['starting_balance']:,}")
    print(f"Leverage: {PAPER_TRADING_CONFIG['futures_leverage']}x")
    print(f"Fee: {PAPER_TRADING_CONFIG['fee']*100}%")
    print()
    print(f"Strategy: {PAPER_TRADING_CONFIG['strategy_name']}")
    print()
    print("Backtest Periods:")
    for period_name, period_config in BACKTEST_PERIODS.items():
        print(f"  {period_name}: {period_config['start']} → {period_config['end']}")
        print(f"    {period_config['description']}")
    print()
    print("Next Steps:")
    print("  1. Run test backtest: python test_strategies.py")
    print("  2. Review results and compare")
    print("  3. Start paper trading")
    print("=" * 80)
