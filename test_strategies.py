#!/usr/bin/env python3
"""
Strategy Comparison Test Script
================================

Tests both strategies and compares results:
1. FractalTrend10x (Baseline)
2. FractalTrendAdaptive (Dynamic)

Usage:
    python test_strategies.py
"""

import subprocess
import json
from datetime import datetime


def run_jesse_backtest(strategy_name, start_date, end_date):
    """
    Run Jesse backtest for a strategy
    """
    print(f"\n{'='*80}")
    print(f"Testing: {strategy_name}")
    print(f"Period: {start_date} → {end_date}")
    print(f"{'='*80}\n")

    cmd = [
        'jesse', 'backtest',
        start_date, end_date,
        '--strategy', strategy_name
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )

        print(result.stdout)

        if result.returncode != 0:
            print(f"❌ Error: {result.stderr}")
            return None

        return {
            'strategy': strategy_name,
            'start': start_date,
            'end': end_date,
            'output': result.stdout
        }

    except subprocess.TimeoutExpired:
        print("⏱️  Timeout - backtest took too long")
        return None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


def compare_results(baseline_result, adaptive_result):
    """
    Compare two strategy results
    """
    print("\n" + "="*80)
    print("COMPARISON: Baseline vs Adaptive")
    print("="*80)

    # This is a simplified comparison
    # In reality, you'd parse Jesse's output for metrics

    print("\nBaseline (FractalTrend10x):")
    print("  Expected: 22.10% ROI (10 months)")
    print("  Actual: [See output above]")

    print("\nAdaptive (FractalTrendAdaptive):")
    print("  Expected: 25-30% ROI (10 months)")
    print("  Actual: [See output above]")

    print("\nKey Metrics to Compare:")
    print("  - ROI: Higher is better")
    print("  - Max Drawdown: Lower is better")
    print("  - Win Rate: Should be ~52%")
    print("  - Profit Factor: Should be >1.3")
    print("  - Sharpe Ratio: Higher is better")

    print("\n" + "="*80)


def main():
    print("="*80)
    print("STRATEGY COMPARISON TEST")
    print("="*80)
    print()
    print("This will test both strategies on 2024 data (10 months)")
    print()

    # Test period
    start_date = '2024-01-01'
    end_date = '2024-10-31'

    # Test baseline
    print("\n[1/2] Testing Baseline Strategy...")
    baseline_result = run_jesse_backtest('FractalTrend10x', start_date, end_date)

    # Test adaptive
    print("\n[2/2] Testing Adaptive Strategy...")
    adaptive_result = run_jesse_backtest('FractalTrendAdaptive', start_date, end_date)

    # Compare
    if baseline_result and adaptive_result:
        compare_results(baseline_result, adaptive_result)
    else:
        print("\n⚠️  Could not complete comparison - check errors above")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nNext Steps:")
    print("1. Review metrics above")
    print("2. If baseline ~22% ROI: ✅ Strategy working correctly")
    print("3. If adaptive > baseline: ✅ Dynamic features helping")
    print("4. If adaptive < baseline: ⚠️  Tune adaptive parameters")
    print()
    print("Ready for paper trading? Run:")
    print("  jesse paper-trade")
    print("="*80)


if __name__ == '__main__':
    main()
