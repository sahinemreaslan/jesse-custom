"""
Parameter Space - Parametre Arama Alanı Tanımlama

Jesse stratejileri için optimize edilebilir parametreleri tanımlar.
"""

from typing import List, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum
import random


class ParameterType(Enum):
    """Parametre tipi"""
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    CHOICE = "choice"


@dataclass
class Parameter:
    """
    Tek bir parametre tanımı.

    Attributes:
        name: Parametre adı (örn: 'rsi_period')
        param_type: Parametre tipi (int, float, bool, choice)
        min_value: Minimum değer (int/float için)
        max_value: Maksimum değer (int/float için)
        step: Adım büyüklüğü (opsiyonel)
        choices: Seçenekler listesi (choice için)
        default: Varsayılan değer
    """
    name: str
    param_type: ParameterType
    min_value: Union[int, float, None] = None
    max_value: Union[int, float, None] = None
    step: Union[int, float, None] = None
    choices: Union[List[Any], None] = None
    default: Any = None

    def random_value(self) -> Any:
        """Rastgele bir değer üret."""
        if self.param_type == ParameterType.INTEGER:
            if self.step:
                # Step'e göre
                values = range(self.min_value, self.max_value + 1, self.step)
                return random.choice(list(values))
            return random.randint(self.min_value, self.max_value)

        elif self.param_type == ParameterType.FLOAT:
            value = random.uniform(self.min_value, self.max_value)
            if self.step:
                # Step'e yuvarla
                value = round(value / self.step) * self.step
            return round(value, 4)

        elif self.param_type == ParameterType.BOOLEAN:
            return random.choice([True, False])

        elif self.param_type == ParameterType.CHOICE:
            return random.choice(self.choices)

        else:
            raise ValueError(f"Unknown parameter type: {self.param_type}")

    def clip_value(self, value: Any) -> Any:
        """Değeri min/max arasında sınırla."""
        if self.param_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
            return max(self.min_value, min(self.max_value, value))
        elif self.param_type == ParameterType.BOOLEAN:
            return bool(value)
        elif self.param_type == ParameterType.CHOICE:
            return value if value in self.choices else random.choice(self.choices)
        return value

    def mutate(self, value: Any, sigma: float = 0.1) -> Any:
        """Değeri mutasyona uğrat."""
        if self.param_type == ParameterType.INTEGER:
            # Gaussian mutation
            range_size = self.max_value - self.min_value
            delta = int(random.gauss(0, range_size * sigma))
            new_value = value + delta
            return self.clip_value(new_value)

        elif self.param_type == ParameterType.FLOAT:
            # Gaussian mutation
            range_size = self.max_value - self.min_value
            delta = random.gauss(0, range_size * sigma)
            new_value = value + delta
            return round(self.clip_value(new_value), 4)

        elif self.param_type == ParameterType.BOOLEAN:
            # Flip with probability
            return not value if random.random() < 0.5 else value

        elif self.param_type == ParameterType.CHOICE:
            # Random choice
            return random.choice(self.choices)

        return value


class ParameterSpace:
    """
    Strateji için parametre arama alanı.

    Example:
        >>> space = ParameterSpace([
        ...     Parameter('rsi_period', ParameterType.INTEGER, 5, 30),
        ...     Parameter('ma_period', ParameterType.INTEGER, 20, 200, step=10),
        ...     Parameter('threshold', ParameterType.FLOAT, 0.5, 2.0),
        ... ])
        >>> chromosome = space.random_chromosome()
        >>> {'rsi_period': 14, 'ma_period': 50, 'threshold': 1.23}
    """

    def __init__(self, parameters: List[Parameter]):
        """
        Args:
            parameters: Parametre listesi
        """
        self.parameters = {p.name: p for p in parameters}
        self.param_names = [p.name for p in parameters]

    def random_chromosome(self) -> dict:
        """Rastgele bir kromozom (parametre seti) oluştur."""
        return {
            name: param.random_value()
            for name, param in self.parameters.items()
        }

    def mutate_chromosome(self, chromosome: dict, mutation_sigma: float = 0.1) -> dict:
        """Kromozomu mutasyona uğrat."""
        mutated = {}
        for name, value in chromosome.items():
            param = self.parameters[name]
            mutated[name] = param.mutate(value, mutation_sigma)
        return mutated

    def crossover_chromosomes(
        self,
        parent1: dict,
        parent2: dict,
        method: str = 'uniform'
    ) -> Tuple[dict, dict]:
        """
        İki ebeveyn kromozomdan çaprazlama ile çocuklar üret.

        Args:
            parent1: Ebeveyn 1
            parent2: Ebeveyn 2
            method: 'uniform', 'single_point', 'two_point'

        Returns:
            Tuple[dict, dict]: İki çocuk kromozom
        """
        if method == 'uniform':
            # Her gen için rastgele ebeveyn seç
            child1 = {}
            child2 = {}
            for name in self.param_names:
                if random.random() < 0.5:
                    child1[name] = parent1[name]
                    child2[name] = parent2[name]
                else:
                    child1[name] = parent2[name]
                    child2[name] = parent1[name]
            return child1, child2

        elif method == 'single_point':
            # Tek nokta çaprazlama
            point = random.randint(1, len(self.param_names) - 1)
            child1 = {}
            child2 = {}
            for i, name in enumerate(self.param_names):
                if i < point:
                    child1[name] = parent1[name]
                    child2[name] = parent2[name]
                else:
                    child1[name] = parent2[name]
                    child2[name] = parent1[name]
            return child1, child2

        elif method == 'two_point':
            # İki nokta çaprazlama
            point1 = random.randint(1, len(self.param_names) - 2)
            point2 = random.randint(point1 + 1, len(self.param_names) - 1)
            child1 = {}
            child2 = {}
            for i, name in enumerate(self.param_names):
                if point1 <= i < point2:
                    child1[name] = parent2[name]
                    child2[name] = parent1[name]
                else:
                    child1[name] = parent1[name]
                    child2[name] = parent2[name]
            return child1, child2

        else:
            raise ValueError(f"Unknown crossover method: {method}")

    def validate_chromosome(self, chromosome: dict) -> bool:
        """Kromozomun geçerli olup olmadığını kontrol et."""
        # Tüm parametreler mevcut mu?
        if set(chromosome.keys()) != set(self.param_names):
            return False

        # Her değer geçerli mi?
        for name, value in chromosome.items():
            param = self.parameters[name]
            if param.param_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
                if not (param.min_value <= value <= param.max_value):
                    return False
            elif param.param_type == ParameterType.CHOICE:
                if value not in param.choices:
                    return False

        return True

    def __len__(self) -> int:
        return len(self.parameters)

    def __repr__(self) -> str:
        return f"ParameterSpace({len(self.parameters)} parameters)"


# Örnek: Dual MA + RSI stratejisi için parametre alanı
def create_dual_ma_rsi_space() -> ParameterSpace:
    """Dual MA + RSI stratejisi için parametre alanı oluştur."""
    return ParameterSpace([
        Parameter('fast_ma', ParameterType.INTEGER, min_value=5, max_value=50, step=1),
        Parameter('slow_ma', ParameterType.INTEGER, min_value=50, max_value=200, step=10),
        Parameter('rsi_period', ParameterType.INTEGER, min_value=7, max_value=28, step=1),
        Parameter('rsi_buy_threshold', ParameterType.INTEGER, min_value=20, max_value=40, step=5),
        Parameter('rsi_sell_threshold', ParameterType.INTEGER, min_value=60, max_value=80, step=5),
        Parameter('use_trend_filter', ParameterType.BOOLEAN),
    ])


# Örnek: Triple EMA + MACD stratejisi için parametre alanı
def create_triple_ema_macd_space() -> ParameterSpace:
    """Triple EMA + MACD stratejisi için parametre alanı oluştur."""
    return ParameterSpace([
        Parameter('ema_fast', ParameterType.INTEGER, min_value=5, max_value=20, step=1),
        Parameter('ema_medium', ParameterType.INTEGER, min_value=20, max_value=50, step=5),
        Parameter('ema_slow', ParameterType.INTEGER, min_value=50, max_value=200, step=10),
        Parameter('macd_fast', ParameterType.INTEGER, min_value=8, max_value=16, step=1),
        Parameter('macd_slow', ParameterType.INTEGER, min_value=20, max_value=30, step=1),
        Parameter('macd_signal', ParameterType.INTEGER, min_value=7, max_value=12, step=1),
    ])


# Örnek: Fraktal stratejisi için parametre alanı
def create_fractal_strategy_space() -> ParameterSpace:
    """Fraktal stratejisi için parametre alanı oluştur."""
    return ParameterSpace([
        Parameter('min_strength', ParameterType.INTEGER, min_value=20, max_value=80, step=5),
        Parameter('trend_ema_period', ParameterType.INTEGER, min_value=30, max_value=100, step=10),
        Parameter('trend_threshold_pct', ParameterType.FLOAT, min_value=0.5, max_value=3.0, step=0.1),
        Parameter('adx_period', ParameterType.INTEGER, min_value=10, max_value=30, step=2),
        Parameter('adx_threshold', ParameterType.INTEGER, min_value=15, max_value=35, step=5),
        Parameter('volume_multiplier', ParameterType.FLOAT, min_value=1.0, max_value=2.0, step=0.1),
        Parameter('tp_percent', ParameterType.FLOAT, min_value=0.1, max_value=1.0, step=0.05),
        Parameter('sl_percent', ParameterType.FLOAT, min_value=0.05, max_value=0.5, step=0.05),
        Parameter('use_trailing_stop', ParameterType.BOOLEAN),
        Parameter('trailing_stop_activation', ParameterType.FLOAT, min_value=0.1, max_value=0.5, step=0.05),
        Parameter('trailing_stop_distance', ParameterType.FLOAT, min_value=0.05, max_value=0.3, step=0.05),
    ])
