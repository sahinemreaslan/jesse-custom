"""
Genetik Algoritma Konfigürasyonu

Jesse stratejileri için GA parametreleri.
"""

# Genetik Algoritma Parametreleri
GA_CONFIG = {
    # Popülasyon ayarları
    'population_size': 100,          # Her jenerasyondaki birey sayısı
    'num_generations': 50,           # Toplam jenerasyon sayısı

    # Evrim operatörleri
    'crossover_prob': 0.7,           # Çaprazlama olasılığı
    'mutation_prob': 0.2,            # Mutasyon olasılığı
    'mutation_sigma': 0.1,           # Mutasyon değişim oranı

    # Seçilim
    'tournament_size': 3,            # Turnuva seçimi için grup büyüklüğü
    'elitism_count': 5,              # En iyi n birey direkt geçer

    # Paralelleştirme
    'use_multiprocessing': True,     # Çoklu işlem kullan
    'num_workers': -1,               # -1 = tüm CPU çekirdekleri

    # Fitness metriği
    'fitness_metric': 'sharpe_ratio',  # sharpe_ratio, total_return, calmar_ratio, composite

    # Fitness ağırlıkları (composite için)
    'fitness_weights': {
        'sharpe_ratio': 0.4,
        'total_return': 0.3,
        'max_drawdown': 0.2,
        'win_rate': 0.1,
    },

    # Kısıtlamalar
    'min_trades': 30,                # Minimum işlem sayısı
    'max_drawdown_threshold': 0.25,  # Maksimum drawdown sınırı
    'min_win_rate': 0.40,            # Minimum win rate

    # Backtest ayarları
    'start_date': '2023-01-01',
    'finish_date': '2024-12-31',

    # Loglama
    'verbose': True,
    'save_all_generations': False,   # Tüm jenerasyonları kaydet
    'save_top_n': 10,                # En iyi n stratejiyi kaydet
}

# Jesse Backtest Ayarları
JESSE_CONFIG = {
    'exchange': 'Binance Futures',
    'symbol': 'BTC-USDT',
    'timeframe': '15m',
    'starting_balance': 10000,
    'fee': 0.0004,  # 0.04%
}
