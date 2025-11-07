"""
Visualization - Görselleştirme Araçları

GA optimizasyon sonuçlarını görselleştirir.
"""

import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any, Optional
from pathlib import Path
import numpy as np


# Seaborn stil ayarları
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 8)


def plot_optimization_results(
    history: Dict[str, List[float]],
    save_path: Optional[str] = None,
    show: bool = True
):
    """
    Optimizasyon sürecini görselleştir.

    Args:
        history: Optimization history
        save_path: Kayıt yolu (opsiyonel)
        show: Göster
    """
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    generations = list(range(len(history['best_fitness'])))

    # 1. Fitness Evolution
    ax1 = axes[0, 0]
    ax1.plot(generations, history['best_fitness'], 'g-', linewidth=2, label='Best')
    ax1.plot(generations, history['avg_fitness'], 'b--', linewidth=1.5, label='Average')
    ax1.plot(generations, history['worst_fitness'], 'r:', linewidth=1, label='Worst')
    ax1.set_xlabel('Generation')
    ax1.set_ylabel('Fitness')
    ax1.set_title('Fitness Evolution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Best Fitness Improvement
    ax2 = axes[0, 1]
    cumulative_best = np.maximum.accumulate(history['best_fitness'])
    ax2.plot(generations, cumulative_best, 'g-', linewidth=2)
    ax2.fill_between(generations, 0, cumulative_best, alpha=0.3, color='green')
    ax2.set_xlabel('Generation')
    ax2.set_ylabel('Best Fitness (Cumulative)')
    ax2.set_title('Best Fitness Improvement')
    ax2.grid(True, alpha=0.3)

    # 3. Fitness Distribution
    ax3 = axes[1, 0]
    ax3.hist(history['best_fitness'], bins=20, alpha=0.7, color='green', edgecolor='black')
    ax3.axvline(np.mean(history['best_fitness']), color='red', linestyle='--', linewidth=2, label='Mean')
    ax3.axvline(np.median(history['best_fitness']), color='blue', linestyle='--', linewidth=2, label='Median')
    ax3.set_xlabel('Fitness')
    ax3.set_ylabel('Frequency')
    ax3.set_title('Best Fitness Distribution')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. Fitness Variance
    ax4 = axes[1, 1]
    fitness_variance = np.array(history['best_fitness']) - np.array(history['worst_fitness'])
    ax4.plot(generations, fitness_variance, 'purple', linewidth=2)
    ax4.fill_between(generations, 0, fitness_variance, alpha=0.3, color='purple')
    ax4.set_xlabel('Generation')
    ax4.set_ylabel('Fitness Spread (Best - Worst)')
    ax4.set_title('Population Diversity')
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"💾 Grafik kaydedildi: {save_path}")

    if show:
        plt.show()
    else:
        plt.close()


def plot_generation_evolution(
    history: Dict[str, List[float]],
    save_path: Optional[str] = None,
    show: bool = True
):
    """
    Jenerasyon evrimini detaylı görselleştir.

    Args:
        history: Optimization history
        save_path: Kayıt yolu
        show: Göster
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    generations = list(range(len(history['best_fitness'])))

    # Fitness aralığı (best - worst)
    best = np.array(history['best_fitness'])
    worst = np.array(history['worst_fitness'])
    avg = np.array(history['avg_fitness'])

    # Aralık gösterimi
    ax.fill_between(generations, worst, best, alpha=0.2, color='blue', label='Fitness Range')

    # Çizgiler
    ax.plot(generations, best, 'g-', linewidth=2.5, label='Best Fitness', marker='o', markersize=4)
    ax.plot(generations, avg, 'b--', linewidth=2, label='Average Fitness')
    ax.plot(generations, worst, 'r:', linewidth=1.5, label='Worst Fitness')

    ax.set_xlabel('Generation', fontsize=12)
    ax.set_ylabel('Fitness Score', fontsize=12)
    ax.set_title('Genetic Algorithm Evolution', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='best')
    ax.grid(True, alpha=0.3)

    # İyileştirme noktalarını işaretle
    improvements = []
    for i in range(1, len(best)):
        if best[i] > best[i-1]:
            improvements.append(i)

    if improvements:
        ax.scatter([generations[i] for i in improvements],
                  [best[i] for i in improvements],
                  color='gold', s=100, marker='*',
                  zorder=5, label='Improvement')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    if show:
        plt.show()
    else:
        plt.close()


def plot_parameter_heatmap(
    top_strategies: List[Dict[str, Any]],
    save_path: Optional[str] = None,
    show: bool = True
):
    """
    En iyi stratejilerin parametrelerini heatmap olarak göster.

    Args:
        top_strategies: En iyi stratejiler listesi
        save_path: Kayıt yolu
        show: Göster
    """
    if not top_strategies:
        print("Heatmap için veri yok.")
        return

    # Parametreleri DataFrame'e çevir
    params = []
    for strategy in top_strategies:
        params.append(strategy['chromosome'])

    import pandas as pd
    df = pd.DataFrame(params)

    # Normalize et (0-1 arası)
    df_norm = (df - df.min()) / (df.max() - df.min())

    # Heatmap
    fig, ax = plt.subplots(figsize=(12, len(top_strategies) * 0.5 + 2))

    sns.heatmap(
        df_norm.T,
        annot=df.T,  # Gerçek değerleri göster
        fmt='.2f',
        cmap='YlGnBu',
        cbar_kws={'label': 'Normalized Value'},
        ax=ax,
        linewidths=0.5
    )

    ax.set_xlabel('Strategy Rank')
    ax.set_ylabel('Parameters')
    ax.set_title('Top Strategies Parameter Heatmap')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    if show:
        plt.show()
    else:
        plt.close()


def plot_equity_curve(
    equity_curve: np.ndarray,
    title: str = 'Equity Curve',
    save_path: Optional[str] = None,
    show: bool = True
):
    """
    Equity curve görselleştir.

    Args:
        equity_curve: Equity curve
        title: Başlık
        save_path: Kayıt yolu
        show: Göster
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(equity_curve, linewidth=2, color='green')
    ax.fill_between(range(len(equity_curve)), 0, equity_curve, alpha=0.3, color='green')

    ax.set_xlabel('Time Period')
    ax.set_ylabel('Portfolio Value')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)

    # Drawdown göster
    cummax = np.maximum.accumulate(equity_curve)
    drawdown = (cummax - equity_curve) / cummax

    ax2 = ax.twinx()
    ax2.fill_between(range(len(drawdown)), 0, -drawdown * 100, alpha=0.3, color='red')
    ax2.set_ylabel('Drawdown (%)', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    if show:
        plt.show()
    else:
        plt.close()
