"""
GA Trading System - Core Modules

Ana modüller:
- DataHandler: Veri yönetimi
- FeatureEngine: Teknik indikatör motoru
- StrategyBase: Temel strateji sınıfı
- Backtester: Backtest motoru
- StrategyOptimizer: Genetik Algoritma optimizasyon (CORE)
- ExecutionEngine: Canlı işlem motoru
- RiskManager: Risk yönetimi
"""

__version__ = "1.0.0"
__author__ = "GA Trading System"

from .data_handler import DataHandler
from .feature_engine import FeatureEngine
from .strategy_base import StrategyBase
from .backtester import Backtester
from .strategy_optimizer import StrategyOptimizer
from .execution_engine import ExecutionEngine
from .risk_manager import RiskManager

__all__ = [
    'DataHandler',
    'FeatureEngine',
    'StrategyBase',
    'Backtester',
    'StrategyOptimizer',
    'ExecutionEngine',
    'RiskManager',
]
