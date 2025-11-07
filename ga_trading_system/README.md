# GA Trading System - Genetik Algoritma Tabanlı Strateji Optimizasyon Sistemi

## 📋 Proje Yapısı

```
ga_trading_system/
├── core/                          # Ana modüller
│   ├── __init__.py
│   ├── data_handler.py           # Veri yönetimi (API, DB)
│   ├── feature_engine.py         # Teknik indikatör motoru
│   ├── strategy_base.py          # Temel strateji sınıfı
│   ├── backtester.py             # Vektörel backtest motoru
│   ├── strategy_optimizer.py    # Genetik Algoritma optimizasyon (CORE)
│   ├── execution_engine.py       # Canlı işlem motoru
│   └── risk_manager.py           # Risk yönetimi
│
├── strategies/                    # Strateji şablonları
│   ├── __init__.py
│   ├── dual_ma_rsi.py            # Dual MA + RSI stratejisi
│   ├── triple_ema_macd.py        # Triple EMA + MACD stratejisi
│   └── custom_strategy.py        # Özel strateji şablonu
│
├── config/                        # Yapılandırma dosyaları
│   ├── config.ini                # Ana konfigürasyon
│   ├── .env.example              # API anahtarları örneği
│   └── ga_params.json            # GA parametreleri
│
├── data/                          # Veri depolama
│   ├── historical/               # Tarihsel veri (CSV, DB)
│   └── cache/                    # Cache dosyaları
│
├── utils/                         # Yardımcı araçlar
│   ├── __init__.py
│   ├── logger.py                 # Loglama sistemi
│   ├── metrics.py                # Performans metrikleri
│   └── visualization.py          # Görselleştirme araçları
│
├── tests/                         # Unit testler
│   ├── test_data_handler.py
│   ├── test_backtester.py
│   └── test_optimizer.py
│
├── results/                       # Optimizasyon sonuçları
│   ├── best_strategies/          # En iyi bulunan stratejiler
│   └── reports/                  # Raporlar ve grafikler
│
├── logs/                          # Log dosyaları
│
├── main_optimizer.py             # Ana optimizasyon çalıştırıcı
├── main_live.py                  # Canlı trading çalıştırıcı
├── requirements.txt              # Python bağımlılıkları
└── README.md                     # Bu dosya
```

## 🎯 Sistemin Temel Felsefesi

Bu sistem **statik, önceden tanımlanmış stratejiler çalıştırmaz**. Sistem kalbi:

**Strateji Optimizasyon Modülü (Genetik Algoritma)** - Verilen strateji şablonları için:
- En kârlı
- En stabil
- En yüksek Sharpe Oranı

parametrelerini **sürekli arar ve keşfeder**.

## 🚀 Çalışma Modları

### 1. Strateji Bulma Modu (Optimization)
```bash
python main_optimizer.py
```
- Genetik Algoritma ile en iyi parametreleri arar
- Backtest sonuçlarını analiz eder
- En iyi stratejiyi kaydeder

### 2. Strateji Uygulama Modu (Live Trading)
```bash
python main_live.py
```
- Bulunan en iyi stratejiyi canlı piyasada çalıştırır
- Risk yönetimi uygular
- Gerçek emirler gönderir

## 📦 Kurulum

```bash
# Virtual environment oluştur
python3.10 -m venv venv
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Konfigürasyonu ayarla
cp config/.env.example config/.env
# .env dosyasını düzenle (API keys vb.)
```

## 🧬 Genetik Algoritma Akışı

```
1. Başlangıç Popülasyonu Oluştur (Rastgele Parametreler)
   ↓
2. Her Kromozom için Fitness Hesapla (Backtest)
   ↓
3. En İyileri Seç (Selection)
   ↓
4. Çaprazlama (Crossover) - Yeni Çocuklar Oluştur
   ↓
5. Mutasyon (Mutation) - Çeşitlilik Ekle
   ↓
6. Yeni Jenerasyon → 2. Adıma Dön
   ↓
7. N Jenerasyon Sonra: En İyi Stratejiyi Kaydet
```

## 📊 Fitness Fonksiyonu Seçenekleri

- **Sharpe Ratio** (Risk-adjusted return)
- **Total Return** (Toplam getiri)
- **Calmar Ratio** (Return / Max Drawdown)
- **Sortino Ratio** (Downside risk odaklı)
- **Custom Composite Score** (Çoklu metrik kombinasyonu)

## 🔧 Teknoloji Yığını

- **Python**: 3.10+
- **Veri**: Pandas, NumPy
- **Borsa API**: ccxt
- **İndikatörler**: pandas_ta
- **Optimizasyon**: DEAP (Distributed Evolutionary Algorithms)
- **Database**: SQLite / InfluxDB
- **Parallelization**: multiprocessing

## 📝 Kullanım Örneği

```python
from core.strategy_optimizer import StrategyOptimizer
from strategies.dual_ma_rsi import DualMaRsiStrategy

# Arama alanını tanımla
search_space = {
    'fast_ma': (5, 50),      # Hızlı MA: 5-50 arası
    'slow_ma': (50, 200),    # Yavaş MA: 50-200 arası
    'rsi_period': (7, 28),   # RSI periyodu
    'rsi_buy': (20, 40),     # RSI alım eşiği
    'rsi_sell': (60, 80)     # RSI satım eşiği
}

# Optimizer'ı çalıştır
optimizer = StrategyOptimizer(
    strategy_template=DualMaRsiStrategy,
    search_space=search_space,
    fitness_metric='sharpe_ratio'
)

best_params = optimizer.run(
    population_size=100,
    generations=50,
    parallel=True
)

print(f"En iyi parametreler: {best_params}")
```

## ⚠️ Önemli Notlar

### Lookahead Bias Prevention
Sistem, **kesinlikle** geleceği görme hatasına (lookahead bias) düşmez. Tüm sinyaller sadece o ana kadar olan veriyle üretilir.

### Risk Yönetimi
Canlı trading başlamadan önce **mutlaka**:
- Paper trading ile test edin
- Stop-loss ayarlarını doğrulayın
- Position size limitlerini belirleyin
- Maximum drawdown limitlerini ayarlayın

### Backtesting ≠ Canlı Performans
Backtest sonuçları, gelecek performansı garanti etmez. Slippage, komisyonlar ve piyasa likiditesi gerçek sonuçları etkileyebilir.

## 📈 Performans Metrikleri

Sistem şu metrikleri hesaplar:
- Total Return (%)
- Sharpe Ratio
- Sortino Ratio
- Maximum Drawdown (%)
- Win Rate (%)
- Profit Factor
- Average Win / Average Loss
- Number of Trades

## 🔐 Güvenlik

- API anahtarları **asla** kod içinde olmamalı
- `.env` dosyası **git'e** eklenmemeli (.gitignore)
- Live trading için test hesabı kullanın
- Rate limiting uygulayın
- Error handling ve retry mekanizmaları kullanın

## 📚 Daha Fazla Bilgi

- [Genetik Algoritma Detayları](docs/genetic_algorithm.md)
- [Strateji Şablonu Oluşturma](docs/creating_strategies.md)
- [Backtesting Metodolojisi](docs/backtesting.md)
- [Live Trading Kurulumu](docs/live_trading.md)

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/yeni-ozellik`)
3. Commit yapın (`git commit -am 'Yeni özellik ekle'`)
4. Push edin (`git push origin feature/yeni-ozellik`)
5. Pull Request oluşturun

## 📄 Lisans

MIT License - Detaylar için `LICENSE` dosyasına bakın.

## ⚡ Hızlı Başlangıç Kontrol Listesi

- [ ] Python 3.10+ kurulu mu?
- [ ] Virtual environment oluşturuldu mu?
- [ ] `requirements.txt` yüklendi mi?
- [ ] `config/.env` dosyası oluşturuldu mu?
- [ ] API anahtarları ayarlandı mı?
- [ ] Test verisi indirildi mi?
- [ ] `main_optimizer.py` başarıyla çalışıyor mu?
- [ ] Paper trading test edildi mi?

---

**Not:** Bu sistem, eğitim ve araştırma amaçlıdır. Gerçek para ile işlem yapmadan önce sistemi iyice test edin ve risk yönetimi kurallarını uygulayın.
