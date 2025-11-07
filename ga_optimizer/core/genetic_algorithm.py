"""
Genetic Algorithm - Genetik Algoritma Motoru

Jesse stratejileri için parametre optimizasyonu yapan GA engine.

Bu sistem:
- Rastgele popülasyon oluşturur
- Her bireyin fitness'ini hesaplar (Jesse backtest)
- Selection, crossover, mutation ile evrim gerçekleştirir
- En iyi parametreleri bulur

Author: GA Trading System
"""

import random
import time
from typing import List, Dict, Any, Tuple, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import copy
import json
from pathlib import Path
from datetime import datetime

from .parameter_space import ParameterSpace
from .fitness_evaluator import FitnessEvaluator


@dataclass
class Individual:
    """
    Bir birey (kromozom + fitness).

    Attributes:
        chromosome: Parametre seti
        fitness: Fitness skoru
        metrics: Detaylı metrikler
        generation: Hangi jenerasyonda oluşturuldu
    """
    chromosome: Dict[str, Any]
    fitness: float = -999999.0
    metrics: Dict[str, Any] = None
    generation: int = 0

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}

    def __lt__(self, other):
        """Sorting için."""
        return self.fitness < other.fitness

    def __repr__(self):
        return f"Individual(fitness={self.fitness:.4f}, gen={self.generation})"


class GeneticAlgorithm:
    """
    Genetik Algoritma ana sınıfı.

    Example:
        >>> from ga_optimizer.core import GeneticAlgorithm, ParameterSpace, Parameter
        >>> space = ParameterSpace([...])
        >>> ga = GeneticAlgorithm(
        ...     parameter_space=space,
        ...     strategy_name='MyStrategy',
        ...     population_size=100,
        ...     num_generations=50
        ... )
        >>> best_individual = ga.run()
        >>> print(best_individual.chromosome)
    """

    def __init__(
        self,
        parameter_space: ParameterSpace,
        strategy_name: str,
        start_date: str,
        finish_date: str,
        population_size: int = 100,
        num_generations: int = 50,
        crossover_prob: float = 0.7,
        mutation_prob: float = 0.2,
        mutation_sigma: float = 0.1,
        tournament_size: int = 3,
        elitism_count: int = 5,
        fitness_metric: str = 'sharpe_ratio',
        fitness_weights: Optional[Dict[str, float]] = None,
        min_trades: int = 30,
        max_drawdown_threshold: float = 0.25,
        min_win_rate: float = 0.40,
        use_multiprocessing: bool = True,
        num_workers: int = -1,
        verbose: bool = True,
        save_dir: str = 'ga_optimizer/results',
        save_all_generations: bool = False,
        save_top_n: int = 10,
    ):
        """
        Args:
            parameter_space: Parametre arama alanı
            strategy_name: Jesse strateji adı
            start_date: Backtest başlangıç
            finish_date: Backtest bitiş
            population_size: Popülasyon büyüklüğü
            num_generations: Jenerasyon sayısı
            crossover_prob: Çaprazlama olasılığı
            mutation_prob: Mutasyon olasılığı
            mutation_sigma: Mutasyon değişim oranı
            tournament_size: Turnuva seçimi grup büyüklüğü
            elitism_count: Elite birey sayısı
            fitness_metric: Ana fitness metriği
            fitness_weights: Composite için ağırlıklar
            min_trades: Minimum işlem sayısı
            max_drawdown_threshold: Max drawdown sınırı
            min_win_rate: Min win rate
            use_multiprocessing: Paralel işlem kullan
            num_workers: İşçi sayısı (-1 = tüm CPU)
            verbose: Detaylı çıktı
            save_dir: Sonuçları kaydet
            save_all_generations: Tüm jenerasyonları kaydet
            save_top_n: En iyi N'i kaydet
        """
        self.parameter_space = parameter_space
        self.strategy_name = strategy_name
        self.start_date = start_date
        self.finish_date = finish_date

        # GA parametreleri
        self.population_size = population_size
        self.num_generations = num_generations
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.mutation_sigma = mutation_sigma
        self.tournament_size = tournament_size
        self.elitism_count = elitism_count

        # Fitness evaluator
        self.evaluator = FitnessEvaluator(
            strategy_name=strategy_name,
            start_date=start_date,
            finish_date=finish_date,
            fitness_metric=fitness_metric,
            fitness_weights=fitness_weights,
            min_trades=min_trades,
            max_drawdown_threshold=max_drawdown_threshold,
            min_win_rate=min_win_rate,
            verbose=False,  # GA verbose olursa zaten gösterir
        )

        # Parallelization
        self.use_multiprocessing = use_multiprocessing
        self.num_workers = num_workers if num_workers > 0 else mp.cpu_count()

        # Loglama ve kaydetme
        self.verbose = verbose
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.save_all_generations = save_all_generations
        self.save_top_n = save_top_n

        # Evrim history
        self.history = {
            'best_fitness': [],
            'avg_fitness': [],
            'worst_fitness': [],
            'best_individuals': [],
        }

        # En iyi birey
        self.best_individual: Optional[Individual] = None

        # Random seed
        random.seed(42)

    def run(self) -> Individual:
        """
        Genetik Algoritma'yı çalıştır.

        Returns:
            Individual: En iyi bulunan birey
        """
        start_time = time.time()

        if self.verbose:
            print("=" * 80)
            print("🧬 GENETİK ALGORİTMA BAŞLADI")
            print("=" * 80)
            print(f"Strateji: {self.strategy_name}")
            print(f"Parametre Sayısı: {len(self.parameter_space)}")
            print(f"Popülasyon: {self.population_size}")
            print(f"Jenerasyon: {self.num_generations}")
            print(f"Fitness Metriği: {self.evaluator.fitness_metric}")
            print(f"Paralelleştirme: {'Evet' if self.use_multiprocessing else 'Hayır'}")
            if self.use_multiprocessing:
                print(f"İşçi Sayısı: {self.num_workers}")
            print("=" * 80)

        # 1. Başlangıç popülasyonu oluştur
        population = self._initialize_population()

        # 2. Evrim döngüsü
        for generation in range(self.num_generations):
            gen_start = time.time()

            # Fitness hesapla
            population = self._evaluate_population(population, generation)

            # İstatistikleri kaydet
            self._record_statistics(population, generation)

            # Sonraki jenerasyon oluştur (son jenerasyon hariç)
            if generation < self.num_generations - 1:
                population = self._evolve_population(population, generation)

            # Jenerasyon raporu
            gen_time = time.time() - gen_start
            if self.verbose:
                self._print_generation_report(generation, population, gen_time)

            # Jenerasyonu kaydet
            if self.save_all_generations:
                self._save_generation(population, generation)

        # 3. En iyi bireyi kaydet
        self.best_individual = max(population, key=lambda x: x.fitness)
        self._save_best_results()

        total_time = time.time() - start_time

        if self.verbose:
            print("=" * 80)
            print("✅ GENETİK ALGORİTMA TAMAMLANDI")
            print("=" * 80)
            print(f"Toplam Süre: {total_time:.2f} saniye")
            print(f"En İyi Fitness: {self.best_individual.fitness:.4f}")
            print(f"En İyi Parametreler:")
            for key, value in self.best_individual.chromosome.items():
                print(f"  {key}: {value}")
            print("=" * 80)

        return self.best_individual

    def _initialize_population(self) -> List[Individual]:
        """Rastgele başlangıç popülasyonu oluştur."""
        population = []
        for _ in range(self.population_size):
            chromosome = self.parameter_space.random_chromosome()
            individual = Individual(chromosome=chromosome, generation=0)
            population.append(individual)
        return population

    def _evaluate_population(
        self,
        population: List[Individual],
        generation: int
    ) -> List[Individual]:
        """
        Popülasyonun fitness'ini hesapla.

        Args:
            population: Popülasyon
            generation: Jenerasyon numarası

        Returns:
            List[Individual]: Fitness'i hesaplanmış popülasyon
        """
        if self.use_multiprocessing and len(population) > 1:
            # Paralel fitness hesaplama
            population = self._evaluate_parallel(population, generation)
        else:
            # Seri fitness hesaplama
            for individual in population:
                fitness, metrics = self.evaluator.evaluate(individual.chromosome)
                individual.fitness = fitness
                individual.metrics = metrics
                individual.generation = generation

        return population

    def _evaluate_parallel(
        self,
        population: List[Individual],
        generation: int
    ) -> List[Individual]:
        """Paralel fitness hesaplama."""
        # TODO: Multiprocessing ile Jesse backtest çalıştırma
        # Şimdilik seri çalıştır
        for individual in population:
            fitness, metrics = self.evaluator.evaluate(individual.chromosome)
            individual.fitness = fitness
            individual.metrics = metrics
            individual.generation = generation

        return population

    def _evolve_population(
        self,
        population: List[Individual],
        generation: int
    ) -> List[Individual]:
        """
        Yeni jenerasyon oluştur (Selection + Crossover + Mutation).

        Args:
            population: Mevcut popülasyon
            generation: Jenerasyon numarası

        Returns:
            List[Individual]: Yeni popülasyon
        """
        # Popülasyonu fitness'e göre sırala
        population.sort(key=lambda x: x.fitness, reverse=True)

        # Yeni popülasyon
        new_population = []

        # 1. Elitism: En iyi N'i direkt koru
        elites = population[:self.elitism_count]
        new_population.extend([copy.deepcopy(ind) for ind in elites])

        # 2. Selection + Crossover + Mutation ile kalan yerleri doldur
        while len(new_population) < self.population_size:
            # Selection: Turnuva seçimi ile 2 ebeveyn seç
            parent1 = self._tournament_selection(population)
            parent2 = self._tournament_selection(population)

            # Crossover
            if random.random() < self.crossover_prob:
                child1_chromo, child2_chromo = self.parameter_space.crossover_chromosomes(
                    parent1.chromosome,
                    parent2.chromosome,
                    method='uniform'
                )
            else:
                # Crossover olmazsa ebeveynleri kopyala
                child1_chromo = copy.deepcopy(parent1.chromosome)
                child2_chromo = copy.deepcopy(parent2.chromosome)

            # Mutation
            if random.random() < self.mutation_prob:
                child1_chromo = self.parameter_space.mutate_chromosome(
                    child1_chromo,
                    self.mutation_sigma
                )
            if random.random() < self.mutation_prob:
                child2_chromo = self.parameter_space.mutate_chromosome(
                    child2_chromo,
                    self.mutation_sigma
                )

            # Çocukları ekle
            new_population.append(Individual(
                chromosome=child1_chromo,
                generation=generation + 1
            ))
            if len(new_population) < self.population_size:
                new_population.append(Individual(
                    chromosome=child2_chromo,
                    generation=generation + 1
                ))

        return new_population

    def _tournament_selection(self, population: List[Individual]) -> Individual:
        """
        Turnuva seçimi.

        Args:
            population: Popülasyon

        Returns:
            Individual: Seçilen birey
        """
        tournament = random.sample(population, self.tournament_size)
        winner = max(tournament, key=lambda x: x.fitness)
        return winner

    def _record_statistics(self, population: List[Individual], generation: int):
        """İstatistikleri kaydet."""
        fitnesses = [ind.fitness for ind in population]
        best_ind = max(population, key=lambda x: x.fitness)

        self.history['best_fitness'].append(max(fitnesses))
        self.history['avg_fitness'].append(sum(fitnesses) / len(fitnesses))
        self.history['worst_fitness'].append(min(fitnesses))
        self.history['best_individuals'].append(best_ind)

    def _print_generation_report(
        self,
        generation: int,
        population: List[Individual],
        gen_time: float
    ):
        """Jenerasyon raporu yazdır."""
        fitnesses = [ind.fitness for ind in population]
        best_ind = max(population, key=lambda x: x.fitness)

        print(f"\n📊 Jenerasyon {generation + 1}/{self.num_generations}")
        print(f"   En İyi Fitness: {max(fitnesses):.4f}")
        print(f"   Ortalama Fitness: {sum(fitnesses) / len(fitnesses):.4f}")
        print(f"   En Kötü Fitness: {min(fitnesses):.4f}")
        print(f"   Süre: {gen_time:.2f}s")

        # En iyi bireyin metriklerini göster
        if best_ind.metrics:
            print(f"   📈 En İyi Birey Metrikleri:")
            print(f"      Sharpe: {best_ind.metrics.get('sharpe_ratio', 0):.2f}")
            print(f"      Return: {best_ind.metrics.get('total_return', 0):.2%}")
            print(f"      Max DD: {best_ind.metrics.get('max_drawdown', 0):.2%}")
            print(f"      Win Rate: {best_ind.metrics.get('win_rate', 0):.2%}")
            print(f"      Trades: {best_ind.metrics.get('total_trades', 0)}")

    def _save_generation(self, population: List[Individual], generation: int):
        """Jenerasyonu kaydet."""
        gen_dir = self.save_dir / 'generations'
        gen_dir.mkdir(exist_ok=True)

        filename = gen_dir / f'generation_{generation:03d}.json'
        data = {
            'generation': generation,
            'population_size': len(population),
            'individuals': [
                {
                    'chromosome': ind.chromosome,
                    'fitness': ind.fitness,
                    'metrics': ind.metrics,
                }
                for ind in population
            ]
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def _save_best_results(self):
        """En iyi sonuçları kaydet."""
        # En iyi popülasyon
        all_best = self.history['best_individuals']
        all_best.sort(key=lambda x: x.fitness, reverse=True)
        top_n = all_best[:self.save_top_n]

        # Top N'i kaydet
        top_n_file = self.save_dir / 'top_strategies.json'
        data = {
            'strategy_name': self.strategy_name,
            'optimization_date': datetime.now().isoformat(),
            'total_generations': self.num_generations,
            'population_size': self.population_size,
            'fitness_metric': self.evaluator.fitness_metric,
            'top_strategies': [
                {
                    'rank': i + 1,
                    'fitness': ind.fitness,
                    'chromosome': ind.chromosome,
                    'metrics': ind.metrics,
                    'generation': ind.generation,
                }
                for i, ind in enumerate(top_n)
            ]
        }

        with open(top_n_file, 'w') as f:
            json.dump(data, f, indent=2)

        # History kaydet
        history_file = self.save_dir / 'optimization_history.json'
        with open(history_file, 'w') as f:
            json.dump({
                'best_fitness': self.history['best_fitness'],
                'avg_fitness': self.history['avg_fitness'],
                'worst_fitness': self.history['worst_fitness'],
            }, f, indent=2)

        if self.verbose:
            print(f"\n💾 Sonuçlar kaydedildi: {self.save_dir}")

    def get_best_chromosome(self) -> Dict[str, Any]:
        """En iyi kromozomu al."""
        if self.best_individual:
            return self.best_individual.chromosome
        return {}

    def get_optimization_history(self) -> Dict:
        """Optimizasyon geçmişini al."""
        return self.history

    def __repr__(self) -> str:
        return (
            f"GeneticAlgorithm(strategy={self.strategy_name}, "
            f"pop={self.population_size}, gen={self.num_generations})"
        )
