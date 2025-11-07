"""
Metrics - Performans Metrikleri Hesaplama

Backtest ve optimizasyon metriklerini hesaplar.
"""

import numpy as np
from typing import Dict, List, Any
import pandas as pd


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365
) -> float:
    """
    Sharpe oranı hesapla.

    Args:
        returns: Günlük/periyodik getiriler
        risk_free_rate: Risksiz faiz oranı (yıllık)
        periods_per_year: Yılda kaç periyot

    Returns:
        float: Sharpe oranı
    """
    if len(returns) == 0:
        return 0.0

    excess_returns = returns - (risk_free_rate / periods_per_year)
    if np.std(excess_returns) == 0:
        return 0.0

    sharpe = np.mean(excess_returns) / np.std(excess_returns)
    sharpe_annualized = sharpe * np.sqrt(periods_per_year)

    return sharpe_annualized


def calculate_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365
) -> float:
    """
    Sortino oranı hesapla (downside risk odaklı).

    Args:
        returns: Günlük/periyodik getiriler
        risk_free_rate: Risksiz faiz oranı
        periods_per_year: Yılda kaç periyot

    Returns:
        float: Sortino oranı
    """
    if len(returns) == 0:
        return 0.0

    excess_returns = returns - (risk_free_rate / periods_per_year)
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0 or np.std(downside_returns) == 0:
        return 0.0

    sortino = np.mean(excess_returns) / np.std(downside_returns)
    sortino_annualized = sortino * np.sqrt(periods_per_year)

    return sortino_annualized


def calculate_max_drawdown(equity_curve: np.ndarray) -> float:
    """
    Maksimum drawdown hesapla.

    Args:
        equity_curve: Equity curve

    Returns:
        float: Max drawdown (pozitif değer, örn: 0.25 = %25 düşüş)
    """
    if len(equity_curve) == 0:
        return 0.0

    cummax = np.maximum.accumulate(equity_curve)
    drawdown = (cummax - equity_curve) / cummax

    return np.max(drawdown)


def calculate_calmar_ratio(
    total_return: float,
    max_drawdown: float
) -> float:
    """
    Calmar oranı hesapla (Return / Max Drawdown).

    Args:
        total_return: Toplam getiri
        max_drawdown: Maksimum drawdown

    Returns:
        float: Calmar oranı
    """
    if max_drawdown == 0:
        return 0.0
    return total_return / max_drawdown


def calculate_win_rate(trades: List[Dict[str, Any]]) -> float:
    """
    Kazanma oranı hesapla.

    Args:
        trades: İşlem listesi [{'pnl': ...}, ...]

    Returns:
        float: Win rate (0-1 arası)
    """
    if len(trades) == 0:
        return 0.0

    winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
    return winning_trades / len(trades)


def calculate_profit_factor(trades: List[Dict[str, Any]]) -> float:
    """
    Profit factor hesapla (Total Win / Total Loss).

    Args:
        trades: İşlem listesi

    Returns:
        float: Profit factor
    """
    if len(trades) == 0:
        return 0.0

    total_win = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
    total_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))

    if total_loss == 0:
        return float('inf') if total_win > 0 else 0.0

    return total_win / total_loss


def calculate_expectancy(trades: List[Dict[str, Any]]) -> float:
    """
    Beklenen kazanç (expectancy) hesapla.

    Args:
        trades: İşlem listesi

    Returns:
        float: Expectancy
    """
    if len(trades) == 0:
        return 0.0

    win_rate = calculate_win_rate(trades)
    winning_trades = [t['pnl'] for t in trades if t.get('pnl', 0) > 0]
    losing_trades = [t['pnl'] for t in trades if t.get('pnl', 0) < 0]

    avg_win = np.mean(winning_trades) if winning_trades else 0.0
    avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0.0

    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    return expectancy


def calculate_metrics(
    equity_curve: np.ndarray,
    returns: np.ndarray,
    trades: List[Dict[str, Any]],
    starting_capital: float = 10000.0
) -> Dict[str, float]:
    """
    Tüm metrikleri hesapla.

    Args:
        equity_curve: Equity curve
        returns: Getiri serisi
        trades: İşlem listesi
        starting_capital: Başlangıç sermayesi

    Returns:
        Dict: Tüm metrikler
    """
    total_return = (equity_curve[-1] - starting_capital) / starting_capital if len(equity_curve) > 0 else 0.0
    max_dd = calculate_max_drawdown(equity_curve)

    return {
        'total_return': total_return,
        'sharpe_ratio': calculate_sharpe_ratio(returns),
        'sortino_ratio': calculate_sortino_ratio(returns),
        'max_drawdown': max_dd,
        'calmar_ratio': calculate_calmar_ratio(total_return, max_dd),
        'win_rate': calculate_win_rate(trades),
        'profit_factor': calculate_profit_factor(trades),
        'expectancy': calculate_expectancy(trades),
        'total_trades': len(trades),
    }
