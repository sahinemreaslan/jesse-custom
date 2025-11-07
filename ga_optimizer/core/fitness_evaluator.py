"""
Fitness Evaluator - Strateji Performans Değerlendirmesi

Jesse backtest çalıştırıp fitness skorları hesaplar.
"""

import os
import sys
from typing import Dict, Any, Tuple, Optional
import subprocess
import json
import tempfile
from pathlib import Path
import numpy as np


class FitnessEvaluator:
    """
    Genetik Algoritma için fitness değerlendirme sınıfı.

    Jesse backtest engine kullanarak strateji performansını değerlendirir.
    """

    def __init__(
        self,
        strategy_name: str,
        start_date: str,
        finish_date: str,
        exchange: str = 'Binance Futures',
        symbol: str = 'BTC-USDT',
        timeframe: str = '15m',
        fitness_metric: str = 'sharpe_ratio',
        fitness_weights: Optional[Dict[str, float]] = None,
        min_trades: int = 30,
        max_drawdown_threshold: float = 0.25,
        min_win_rate: float = 0.40,
        verbose: bool = False
    ):
        """
        Args:
            strategy_name: Strateji sınıfı adı (örn: 'GAOptimizedStrategy')
            start_date: Backtest başlangıç tarihi (YYYY-MM-DD)
            finish_date: Backtest bitiş tarihi (YYYY-MM-DD)
            exchange: Exchange adı
            symbol: Trading çifti
            timeframe: Zaman dilimi
            fitness_metric: Ana metrik ('sharpe_ratio', 'total_return', 'calmar_ratio', 'composite')
            fitness_weights: Composite metrik için ağırlıklar
            min_trades: Minimum işlem sayısı kısıtı
            max_drawdown_threshold: Maksimum drawdown sınırı
            min_win_rate: Minimum win rate
            verbose: Detaylı çıktı
        """
        self.strategy_name = strategy_name
        self.start_date = start_date
        self.finish_date = finish_date
        self.exchange = exchange
        self.symbol = symbol
        self.timeframe = timeframe
        self.fitness_metric = fitness_metric
        self.fitness_weights = fitness_weights or {
            'sharpe_ratio': 0.4,
            'total_return': 0.3,
            'max_drawdown': 0.2,
            'win_rate': 0.1,
        }
        self.min_trades = min_trades
        self.max_drawdown_threshold = max_drawdown_threshold
        self.min_win_rate = min_win_rate
        self.verbose = verbose

        # Backtest sonuçlarını cache'le (aynı parametreler için tekrar çalıştırma)
        self.cache = {}

    def evaluate(self, parameters: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """
        Verilen parametrelerle stratejiyi değerlendir.

        Args:
            parameters: Strateji parametreleri (kromozom)

        Returns:
            Tuple[float, Dict]: (Fitness skoru, Detaylı metrikler)
        """
        # Cache kontrolü
        param_key = self._dict_to_key(parameters)
        if param_key in self.cache:
            if self.verbose:
                print(f"Cache'den alındı: {param_key[:30]}...")
            return self.cache[param_key]

        # Jesse backtest çalıştır
        metrics = self._run_jesse_backtest(parameters)

        # Geçersiz sonuç kontrolü
        if metrics is None or not self._is_valid_result(metrics):
            fitness = -999999.0  # Çok kötü fitness (elenir)
            metrics = metrics or {}
            self.cache[param_key] = (fitness, metrics)
            return fitness, metrics

        # Fitness hesapla
        fitness = self._calculate_fitness(metrics)

        # Cache'e kaydet
        self.cache[param_key] = (fitness, metrics)

        return fitness, metrics

    def _run_jesse_backtest(self, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Jesse backtest çalıştır ve metrikleri al.

        Args:
            parameters: Strateji parametreleri

        Returns:
            Dict: Backtest metrikleri veya None
        """
        try:
            # Parametreleri geçici bir config dosyasına yaz
            temp_config = self._create_temp_config(parameters)

            # Jesse backtest komutunu çalıştır
            # NOT: Jesse'nin CLI'sini kullanıyoruz
            cmd = [
                'jesse', 'backtest',
                self.start_date,
                self.finish_date,
                '--json',  # JSON output
                '--skip-confirmation',  # Onay isteme
            ]

            # Çalıştır
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 dakika timeout
                cwd=os.getcwd(),
                env={**os.environ, 'GA_PARAMS': json.dumps(parameters)}
            )

            if result.returncode != 0:
                if self.verbose:
                    print(f"Backtest hatası: {result.stderr}")
                return None

            # JSON çıktısını parse et
            metrics = self._parse_jesse_output(result.stdout)

            # Cleanup
            if temp_config and os.path.exists(temp_config):
                os.remove(temp_config)

            return metrics

        except subprocess.TimeoutExpired:
            if self.verbose:
                print("Backtest timeout!")
            return None
        except Exception as e:
            if self.verbose:
                print(f"Backtest exception: {e}")
            return None

    def _create_temp_config(self, parameters: Dict[str, Any]) -> Optional[str]:
        """
        Parametreler için geçici config dosyası oluştur.

        Not: Jesse stratejisi environment variable'dan parametreleri okuyacak.
        """
        # Jesse'de parametreler strategy sınıfından okunur
        # Environment variable ile geçiyoruz
        return None

    def _parse_jesse_output(self, output: str) -> Optional[Dict[str, Any]]:
        """
        Jesse JSON çıktısını parse et.

        Args:
            output: Jesse stdout çıktısı

        Returns:
            Dict: Metrikler
        """
        try:
            # Jesse'nin JSON output formatını parse et
            # Genelde son satırda JSON olur
            lines = output.strip().split('\n')
            for line in reversed(lines):
                if line.startswith('{'):
                    data = json.loads(line)
                    return self._extract_metrics(data)
            return None
        except Exception as e:
            if self.verbose:
                print(f"JSON parse hatası: {e}")
            return None

    def _extract_metrics(self, jesse_output: Dict) -> Dict[str, Any]:
        """
        Jesse çıktısından metrikleri çıkar.

        Args:
            jesse_output: Jesse JSON output

        Returns:
            Dict: Standartlaştırılmış metrikler
        """
        # Jesse'nin metric isimleri
        return {
            'total_return': jesse_output.get('net_profit_percentage', 0) / 100,
            'sharpe_ratio': jesse_output.get('sharpe_ratio', 0),
            'calmar_ratio': jesse_output.get('calmar_ratio', 0),
            'sortino_ratio': jesse_output.get('sortino_ratio', 0),
            'max_drawdown': abs(jesse_output.get('max_drawdown', 0)),
            'win_rate': jesse_output.get('win_rate', 0),
            'total_trades': jesse_output.get('total_trades', 0),
            'profit_factor': jesse_output.get('ratio_avg_win_loss', 0),
            'total_profit': jesse_output.get('net_profit', 0),
            'total_loss': jesse_output.get('total_loss', 0),
            'avg_win': jesse_output.get('average_win', 0),
            'avg_loss': jesse_output.get('average_loss', 0),
        }

    def _is_valid_result(self, metrics: Dict[str, Any]) -> bool:
        """
        Sonuçların kısıtlamaları sağlayıp sağlamadığını kontrol et.

        Args:
            metrics: Backtest metrikleri

        Returns:
            bool: Geçerli mi?
        """
        # Minimum işlem sayısı
        if metrics.get('total_trades', 0) < self.min_trades:
            if self.verbose:
                print(f"❌ Yetersiz işlem: {metrics.get('total_trades', 0)} < {self.min_trades}")
            return False

        # Maximum drawdown
        if metrics.get('max_drawdown', 1.0) > self.max_drawdown_threshold:
            if self.verbose:
                print(f"❌ Çok yüksek drawdown: {metrics.get('max_drawdown', 0):.2%}")
            return False

        # Minimum win rate
        if metrics.get('win_rate', 0) < self.min_win_rate:
            if self.verbose:
                print(f"❌ Düşük win rate: {metrics.get('win_rate', 0):.2%}")
            return False

        return True

    def _calculate_fitness(self, metrics: Dict[str, Any]) -> float:
        """
        Metriklerden fitness skoru hesapla.

        Args:
            metrics: Backtest metrikleri

        Returns:
            float: Fitness skoru (yüksek = iyi)
        """
        if self.fitness_metric == 'sharpe_ratio':
            return metrics.get('sharpe_ratio', 0)

        elif self.fitness_metric == 'total_return':
            return metrics.get('total_return', 0)

        elif self.fitness_metric == 'calmar_ratio':
            return metrics.get('calmar_ratio', 0)

        elif self.fitness_metric == 'sortino_ratio':
            return metrics.get('sortino_ratio', 0)

        elif self.fitness_metric == 'composite':
            # Çoklu metrik kombinasyonu
            return self._composite_fitness(metrics)

        else:
            raise ValueError(f"Unknown fitness metric: {self.fitness_metric}")

    def _composite_fitness(self, metrics: Dict[str, Any]) -> float:
        """
        Composite fitness - Birden fazla metriği birleştirir.

        Args:
            metrics: Backtest metrikleri

        Returns:
            float: Composite fitness skoru
        """
        # Normalize edilmiş metrikler
        sharpe = metrics.get('sharpe_ratio', 0)
        ret = metrics.get('total_return', 0)
        dd = metrics.get('max_drawdown', 1.0)
        wr = metrics.get('win_rate', 0)

        # Sharpe: 0-3 arası normalize et
        norm_sharpe = np.clip(sharpe / 3.0, 0, 1)

        # Return: 0-100% arası normalize et
        norm_return = np.clip(ret, 0, 1)

        # Drawdown: 0-25% arası, düşük iyi (ters)
        norm_dd = np.clip(1 - (dd / self.max_drawdown_threshold), 0, 1)

        # Win rate: 0-100% arası
        norm_wr = wr

        # Ağırlıklı toplam
        fitness = (
            self.fitness_weights['sharpe_ratio'] * norm_sharpe +
            self.fitness_weights['total_return'] * norm_return +
            self.fitness_weights['max_drawdown'] * norm_dd +
            self.fitness_weights['win_rate'] * norm_wr
        )

        return fitness

    def _dict_to_key(self, d: Dict) -> str:
        """Dict'i cache key'e çevir."""
        sorted_items = sorted(d.items())
        return json.dumps(sorted_items, sort_keys=True)

    def clear_cache(self):
        """Cache'i temizle."""
        self.cache = {}

    def get_cache_size(self) -> int:
        """Cache boyutu."""
        return len(self.cache)

    def __repr__(self) -> str:
        return (
            f"FitnessEvaluator(strategy={self.strategy_name}, "
            f"metric={self.fitness_metric}, cache_size={len(self.cache)})"
        )
