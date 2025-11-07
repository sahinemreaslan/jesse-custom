"""
Main GA Optimizer - Genetik Algoritma Optimizer Entry Point

Jesse stratejileri için GA tabanlı parametre optimizasyonu yapar.

Kullanım:
    python main_ga_optimizer.py
"""

import sys
import os
from pathlib import Path

# GA optimizer modüllerini import et
sys.path.insert(0, str(Path(__file__).parent))

from ga_optimizer.core import (
    GeneticAlgorithm,
    ParameterSpace,
    Parameter,
    ParameterType
)
from ga_optimizer.config.ga_config import GA_CONFIG, JESSE_CONFIG
from ga_optimizer.utils import setup_logger, plot_optimization_results, plot_generation_evolution


def create_parameter_space() -> ParameterSpace:
    """
    Optimize edilecek parametre arama alanını tanımla.

    Bu örnek GAOptimizedStrategy için dual MA + RSI parametrelerini tanımlar.
    Kendi stratejiniz için bu fonksiyonu düzenleyin.
    """
    return ParameterSpace([
        Parameter(
            name='fast_ma',
            param_type=ParameterType.INTEGER,
            min_value=5,
            max_value=50,
            step=1,
            default=20
        ),
        Parameter(
            name='slow_ma',
            param_type=ParameterType.INTEGER,
            min_value=50,
            max_value=200,
            step=10,
            default=50
        ),
        Parameter(
            name='rsi_period',
            param_type=ParameterType.INTEGER,
            min_value=7,
            max_value=28,
            step=1,
            default=14
        ),
        Parameter(
            name='rsi_buy_threshold',
            param_type=ParameterType.INTEGER,
            min_value=20,
            max_value=40,
            step=5,
            default=30
        ),
        Parameter(
            name='rsi_sell_threshold',
            param_type=ParameterType.INTEGER,
            min_value=60,
            max_value=80,
            step=5,
            default=70
        ),
        Parameter(
            name='use_trend_filter',
            param_type=ParameterType.BOOLEAN,
            default=True
        ),
    ])


def main():
    """Main optimizer fonksiyonu."""

    # Logger setup
    logger = setup_logger(
        name='ga_optimizer',
        log_file='ga_optimizer/logs/optimization.log',
        level='INFO'
    )

    logger.info("=" * 80)
    logger.info("🧬 GENETIK ALGORITMA OPTIMIZER BAŞLATILIYOR")
    logger.info("=" * 80)

    # Parametre arama alanı
    parameter_space = create_parameter_space()

    logger.info(f"Parametre Sayısı: {len(parameter_space)}")
    logger.info(f"Parametre Listesi:")
    for param_name, param in parameter_space.parameters.items():
        logger.info(f"  - {param_name}: {param.param_type.value} "
                   f"[{param.min_value if param.min_value else ''}-"
                   f"{param.max_value if param.max_value else ''}]")

    # Genetik Algoritma
    ga = GeneticAlgorithm(
        parameter_space=parameter_space,
        strategy_name='GAOptimizedStrategy',
        start_date=GA_CONFIG['start_date'],
        finish_date=GA_CONFIG['finish_date'],
        population_size=GA_CONFIG['population_size'],
        num_generations=GA_CONFIG['num_generations'],
        crossover_prob=GA_CONFIG['crossover_prob'],
        mutation_prob=GA_CONFIG['mutation_prob'],
        mutation_sigma=GA_CONFIG['mutation_sigma'],
        tournament_size=GA_CONFIG['tournament_size'],
        elitism_count=GA_CONFIG['elitism_count'],
        fitness_metric=GA_CONFIG['fitness_metric'],
        fitness_weights=GA_CONFIG['fitness_weights'],
        min_trades=GA_CONFIG['min_trades'],
        max_drawdown_threshold=GA_CONFIG['max_drawdown_threshold'],
        min_win_rate=GA_CONFIG['min_win_rate'],
        use_multiprocessing=GA_CONFIG['use_multiprocessing'],
        num_workers=GA_CONFIG['num_workers'],
        verbose=GA_CONFIG['verbose'],
        save_all_generations=GA_CONFIG['save_all_generations'],
        save_top_n=GA_CONFIG['save_top_n'],
    )

    # Optimize et!
    logger.info("\n🚀 Optimizasyon başlıyor...")

    try:
        best_individual = ga.run()

        logger.info("\n" + "=" * 80)
        logger.info("✅ OPTİMİZASYON TAMAMLANDI!")
        logger.info("=" * 80)

        # En iyi sonuçlar
        logger.info(f"\n📊 EN İYİ STRATEJI:")
        logger.info(f"Fitness Skoru: {best_individual.fitness:.4f}")

        logger.info(f"\n🎯 EN İYİ PARAMETRELER:")
        for key, value in best_individual.chromosome.items():
            logger.info(f"  {key}: {value}")

        if best_individual.metrics:
            logger.info(f"\n📈 PERFORMANS METRİKLERİ:")
            metrics = best_individual.metrics
            logger.info(f"  Total Return: {metrics.get('total_return', 0):.2%}")
            logger.info(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
            logger.info(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.2%}")
            logger.info(f"  Win Rate: {metrics.get('win_rate', 0):.2%}")
            logger.info(f"  Total Trades: {metrics.get('total_trades', 0)}")
            logger.info(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")

        # Görselleştirme
        logger.info("\n📊 Sonuçlar görselleştiriliyor...")

        history = ga.get_optimization_history()

        # Optimization results plot
        plot_optimization_results(
            history=history,
            save_path='ga_optimizer/results/optimization_results.png',
            show=False
        )

        # Generation evolution plot
        plot_generation_evolution(
            history=history,
            save_path='ga_optimizer/results/generation_evolution.png',
            show=False
        )

        logger.info("💾 Grafikler kaydedildi: ga_optimizer/results/")

        logger.info("\n" + "=" * 80)
        logger.info("🎉 TÜM İŞLEMLER TAMAMLANDI!")
        logger.info("=" * 80)

        # Sonuçların yolu
        logger.info(f"\n📁 Sonuçlar:")
        logger.info(f"  - En iyi stratejiler: ga_optimizer/results/top_strategies.json")
        logger.info(f"  - Optimizasyon geçmişi: ga_optimizer/results/optimization_history.json")
        logger.info(f"  - Grafikler: ga_optimizer/results/*.png")
        logger.info(f"  - Log dosyası: ga_optimizer/logs/optimization.log")

        return best_individual

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Kullanıcı tarafından iptal edildi.")
        sys.exit(0)

    except Exception as e:
        logger.error(f"\n❌ Hata oluştu: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    """
    Örnek Kullanım:

    1. Temel kullanım:
        python main_ga_optimizer.py

    2. Config değiştirerek:
        - ga_optimizer/config/ga_config.py dosyasını düzenleyin
        - population_size, num_generations, fitness_metric vb. parametreleri ayarlayın

    3. Farklı strateji için:
        - strategies/ klasörüne yeni strateji ekleyin
        - create_parameter_space() fonksiyonunu düzenleyin
        - strategy_name parametresini değiştirin
    """

    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                                                                ║
    ║      🧬 GENETIK ALGORITMA STRATEJİ OPTİMİZER 🧬                ║
    ║                                                                ║
    ║      Jesse AI Trading Bot için GA tabanlı                     ║
    ║      parametre optimizasyonu sistemi                          ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝
    """)

    best = main()

    print("\n✅ Optimizasyon tamamlandı. Sonuçları kontrol edin!")
    print(f"En iyi fitness: {best.fitness:.4f}")
