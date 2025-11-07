# 🧬 Genetik Algoritma Strateji Optimizer

Jesse AI Trading Bot için **Genetik Algoritma** tabanlı parametre optimizasyon sistemi.

---

## 📌 Sistem Felsefesi

Bu sistem **statik, önceden tanımlanmış stratejiler çalıştırmaz**. Sistem:

✅ Verilen bir strateji şablonu için **en iyi parametreleri arar**
✅ Genetik Algoritma ile **evrim süreciyle** optimum çözümü keşfeder
✅ **Backtest** ile performansı doğrular
✅ **En kârlı, en stabil** veya **en yüksek Sharpe** oranına sahip parametreleri bulur

---

## 🏗️ Sistem Mimarisi

```
Jesse Framework (Backtest Engine, Indicators, Data)
    ↓
┌───────────────────────────────────────────────┐
│   GA OPTIMIZER KATMANI                        │
│                                               │
│   ┌─────────────────────────────────────┐   │
│   │  1. Parameter Space Definition      │   │
│   │     (Arama alanı tanımlama)         │   │
│   └─────────────────────────────────────┘   │
│                  ↓                            │
│   ┌─────────────────────────────────────┐   │
│   │  2. Genetic Algorithm Engine        │   │
│   │     - Random initialization         │   │
│   │     - Fitness evaluation (Backtest) │   │
│   │     - Selection (Tournament)        │   │
│   │     - Crossover (Uniform)           │   │
│   │     - Mutation (Gaussian)           │   │
│   │     - Elitism                       │   │
│   └─────────────────────────────────────┘   │
│                  ↓                            │
│   ┌─────────────────────────────────────┐   │
│   │  3. Best Strategy Output            │   │
│   │     (En iyi parametreler)           │   │
│   └─────────────────────────────────────┘   │
└───────────────────────────────────────────────┘
    ↓
Jesse Strategy (Optimize edilmiş parametrelerle)
```

---

## 📁 Proje Yapısı

```
jesse-custom/
├── ga_optimizer/                    # GA optimizer modülleri
│   ├── core/                       # Core modüller
│   │   ├── __init__.py
│   │   ├── genetic_algorithm.py   # ⭐ Ana GA motoru
│   │   ├── fitness_evaluator.py   # Jesse backtest entegrasyonu
│   │   └── parameter_space.py     # Parametre arama alanı tanımı
│   │
│   ├── utils/                      # Yardımcı araçlar
│   │   ├── __init__.py
│   │   ├── logger.py              # Loglama
│   │   ├── metrics.py             # Performans metrikleri
│   │   └── visualization.py       # Görselleştirme
│   │
│   ├── config/                     # Konfigürasyon
│   │   └── ga_config.py           # GA parametreleri
│   │
│   ├── results/                    # Optimizasyon sonuçları
│   │   ├── top_strategies.json
│   │   ├── optimization_history.json
│   │   └── *.png (grafikler)
│   │
│   └── logs/                       # Log dosyaları
│
├── strategies/                      # Jesse stratejileri
│   ├── __init__.py
│   └── GAOptimizedStrategy.py     # ⭐ Örnek optimize edilebilir strateji
│
├── main_ga_optimizer.py            # ⭐ Ana çalıştırıcı
├── routes.py                        # Jesse routes (güncellendi)
├── config.py                        # Jesse config
├── import_data.py                   # Veri import
│
├── GA_OPTIMIZER_README.md          # Bu dosya
├── GA_ALGORITHM_PSEUDOCODE.md      # Algoritma detayları
└── README.md                        # Ana README
```

---

## 🚀 Hızlı Başlangıç

### 1. Kurulum

```bash
# Virtual environment oluştur (opsiyonel)
python3 -m venv venv
source venv/bin/activate

# Gerekli paketleri yükle
pip install jesse
pip install matplotlib seaborn pandas numpy

# Veritabanı kur
python setup_database.py

# Tarihsel veri indir
python import_data.py
```

### 2. Optimizasyonu Çalıştır

```bash
python main_ga_optimizer.py
```

Bu komut:
- ✅ Rastgele 100 farklı parametre kombinasyonu oluşturur
- ✅ Her birini Jesse backtest ile test eder
- ✅ 50 jenerasyon boyunca evrim uygular
- ✅ En iyi parametreleri bulur ve kaydeder

### 3. Sonuçları İncele

```bash
# En iyi stratejiler
cat ga_optimizer/results/top_strategies.json

# Grafikler
ls ga_optimizer/results/*.png

# Loglar
tail -f ga_optimizer/logs/optimization.log
```

---

## ⚙️ Konfigürasyon

### GA Parametrelerini Ayarlama

`ga_optimizer/config/ga_config.py` dosyasını düzenleyin:

```python
GA_CONFIG = {
    'population_size': 100,          # Popülasyon büyüklüğü
    'num_generations': 50,           # Jenerasyon sayısı

    'crossover_prob': 0.7,           # Çaprazlama olasılığı
    'mutation_prob': 0.2,            # Mutasyon olasılığı
    'mutation_sigma': 0.1,           # Mutasyon şiddeti

    'tournament_size': 3,            # Turnuva seçimi grup büyüklüğü
    'elitism_count': 5,              # Elite birey sayısı

    'fitness_metric': 'sharpe_ratio', # Fitness metriği
    # Seçenekler: sharpe_ratio, total_return, calmar_ratio, composite

    'min_trades': 30,                # Minimum işlem sayısı
    'max_drawdown_threshold': 0.25,  # Max %25 drawdown
    'min_win_rate': 0.40,            # Min %40 win rate

    'use_multiprocessing': True,     # Paralel işlem (ÖNERİLİR)
    'num_workers': -1,               # -1 = tüm CPU çekirdekleri
}
```

### Parametre Arama Alanını Tanımlama

`main_ga_optimizer.py` dosyasındaki `create_parameter_space()` fonksiyonunu düzenleyin:

```python
def create_parameter_space() -> ParameterSpace:
    return ParameterSpace([
        Parameter(
            name='fast_ma',
            param_type=ParameterType.INTEGER,
            min_value=5,
            max_value=50,
            step=1
        ),
        Parameter(
            name='slow_ma',
            param_type=ParameterType.INTEGER,
            min_value=50,
            max_value=200,
            step=10
        ),
        # ... diğer parametreler
    ])
```

---

## 🧬 Genetik Algoritma Nasıl Çalışır?

### Kısa Özet

1. **Başlangıç**: Rastgele 100 parametre seti oluştur
2. **Değerlendirme**: Her seti Jesse backtest ile test et
3. **Seçilim**: En iyi performans gösterenleri seç
4. **Çaprazlama**: İkilileri karıştırarak yeni setler oluştur
5. **Mutasyon**: Küçük değişiklikler ekle (çeşitlilik için)
6. **Tekrar**: 2-5 adımları 50 kez tekrarla
7. **Sonuç**: En iyi bulunan parametreleri kaydet

### Detaylı Pseudocode

Detaylı algoritma akışı için: [GA_ALGORITHM_PSEUDOCODE.md](GA_ALGORITHM_PSEUDOCODE.md)

---

## 📊 Fitness Metrikleri

Sistem 4 farklı fitness metriği destekler:

### 1. **Sharpe Ratio** (Önerilen)
Risk-adjusted return. Yüksek getiri + düşük volatilite.

```python
sharpe = (ortalama_getiri - risksiz_oran) / standart_sapma
```

**Avantajlar:**
- ✅ Risk ve getiriyi dengeler
- ✅ Akademik olarak kabul görmüş
- ✅ Overfit'i önler

### 2. **Total Return**
Toplam getiri (%).

**Avantajlar:**
- ✅ Basit ve anlaşılır
- ✅ Direkt kar odaklı

**Dezavantajlar:**
- ⚠️ Riski göz ardı eder
- ⚠️ Yüksek drawdown'a izin verebilir

### 3. **Calmar Ratio**
Return / Max Drawdown

**Avantajlar:**
- ✅ Drawdown'a odaklanır
- ✅ Risk-averse stratejiler için iyi

### 4. **Composite** (Çoklu Metrik)
Birden fazla metriği birleştirir.

```python
fitness = (
    0.4 * sharpe_normalized +
    0.3 * return_normalized +
    0.2 * (1 - drawdown_normalized) +
    0.1 * win_rate
)
```

**Avantajlar:**
- ✅ Çok yönlü optimizasyon
- ✅ Özelleştirilebilir ağırlıklar

---

## 📈 Örnek Çıktı

```
╔════════════════════════════════════════════════════════════════╗
║      🧬 GENETIK ALGORITMA STRATEJİ OPTİMİZER 🧬                ║
╚════════════════════════════════════════════════════════════════╝

Strateji: GAOptimizedStrategy
Parametre Sayısı: 6
Popülasyon: 100
Jenerasyon: 50
Fitness Metriği: sharpe_ratio
Paralelleştirme: Evet (8 workers)

📊 Jenerasyon 1/50
   En İyi Fitness: 1.8432
   Ortalama Fitness: 0.3421
   En Kötü Fitness: -2.1234
   Süre: 45.2s
   📈 En İyi Birey Metrikleri:
      Sharpe: 1.84
      Return: 23.45%
      Max DD: -8.23%
      Win Rate: 58.30%
      Trades: 87

...

📊 Jenerasyon 50/50
   En İyi Fitness: 2.9876
   Ortalama Fitness: 2.1234
   En Kötü Fitness: 0.8765
   Süre: 42.8s

✅ OPTİMİZASYON TAMAMLANDI!

🎯 EN İYİ PARAMETRELER:
  fast_ma: 18
  slow_ma: 120
  rsi_period: 12
  rsi_buy_threshold: 25
  rsi_sell_threshold: 75
  use_trend_filter: True

📈 PERFORMANS METRİKLERİ:
  Total Return: 47.32%
  Sharpe Ratio: 2.99
  Max Drawdown: -4.56%
  Win Rate: 63.20%
  Total Trades: 142
  Profit Factor: 2.87
```

---

## 🔧 Kendi Stratejinizi Optimize Etme

### Adım 1: Strateji Oluştur

`strategies/MyCustomStrategy.py`:

```python
from jesse.strategies import Strategy
import jesse.indicators as ta
import json
import os

class MyCustomStrategy(Strategy):
    def __init__(self):
        super().__init__()
        # Environment variable'dan parametreleri al
        env_params = os.environ.get('GA_PARAMS')
        if env_params:
            self.params = json.loads(env_params)
        else:
            self.params = self.get_default_params()

    def get_default_params(self):
        return {
            'param1': 10,
            'param2': 20,
            # ...
        }

    def should_long(self):
        # Parametreleri kullan
        indicator = ta.ema(self.candles, self.params['param1'])
        # ...
        return signal

    # ... diğer metodlar
```

### Adım 2: Parametre Alanı Tanımla

`main_ga_optimizer.py`'de:

```python
def create_parameter_space() -> ParameterSpace:
    return ParameterSpace([
        Parameter('param1', ParameterType.INTEGER, 5, 30),
        Parameter('param2', ParameterType.INTEGER, 10, 100),
        # ...
    ])
```

### Adım 3: Çalıştır

```bash
python main_ga_optimizer.py
```

---

## 🎯 Optimizasyon İpuçları

### 1. **Popülasyon ve Jenerasyon Ayarı**

**Küçük arama alanı (< 5 parametre):**
```python
population_size = 50
num_generations = 30
```

**Orta arama alanı (5-10 parametre):**
```python
population_size = 100
num_generations = 50
```

**Büyük arama alanı (> 10 parametre):**
```python
population_size = 200
num_generations = 100
```

### 2. **Fitness Metriği Seçimi**

- **Conservative (Riskten kaçan)**: `calmar_ratio` veya `composite` (max_drawdown ağırlığı yüksek)
- **Balanced (Dengeli)**: `sharpe_ratio` ⭐ ÖNERİLEN
- **Aggressive (Agresif)**: `total_return`

### 3. **Overfitting'i Önleme**

✅ **Min trades constraint kullan**
```python
'min_trades': 30  # Çok az işlem yapan stratejileri ele
```

✅ **Walk-forward validation**
```python
# 2023'te optimize et, 2024'te validate et
start_date = '2023-01-01'
finish_date = '2023-12-31'
```

✅ **Composite fitness kullan**
- Sadece return değil, risk metriklerini de dahil et

### 4. **Performans Optimizasyonu**

✅ **Multiprocessing kullan**
```python
'use_multiprocessing': True
'num_workers': -1  # Tüm CPU çekirdekleri
```

✅ **Cache aktif**
- Fitness evaluator otomatik olarak cache yapar
- Aynı parametreler tekrar test edilmez

---

## 📊 Sonuçları Analiz Etme

### JSON Çıktısı

```bash
cat ga_optimizer/results/top_strategies.json
```

```json
{
  "strategy_name": "GAOptimizedStrategy",
  "optimization_date": "2024-01-15T10:30:00",
  "total_generations": 50,
  "population_size": 100,
  "fitness_metric": "sharpe_ratio",
  "top_strategies": [
    {
      "rank": 1,
      "fitness": 2.9876,
      "chromosome": {
        "fast_ma": 18,
        "slow_ma": 120,
        "rsi_period": 12,
        ...
      },
      "metrics": {
        "total_return": 0.4732,
        "sharpe_ratio": 2.99,
        "max_drawdown": 0.0456,
        ...
      }
    },
    ...
  ]
}
```

### Grafikler

1. **optimization_results.png**: 4 panelli detaylı analiz
2. **generation_evolution.png**: Jenerasyon evrim grafiği

---

## ⚠️ Önemli Notlar

### Lookahead Bias (Geleceği Görme Hatası)

✅ **Sistem otomatik önler**
- Jesse'nin backtest engine'i lookahead bias yapmaz
- Sinyaller sadece o ana kadar olan veriyle üretilir

### Backtesting ≠ Gerçek Performans

⚠️ **Backtest sonuçları gelecek performansı garanti etmez**

Gerçek piyasada:
- Slippage (kayma) olur
- Komisyonlar değişebilir
- Likidite sorunları olabilir
- Piyasa yapısı değişebilir

**Öneriler:**
1. ✅ Paper trading ile test edin
2. ✅ Küçük pozisyonlarla başlayın
3. ✅ Sürekli izleyin ve ayarlayın
4. ✅ Stop-loss kullanın

### Overfitting Riski

GA çok iyi optimize ederse **overfitting** (aşırı uyum) riski vardır.

**Önlemler:**
- ✅ Walk-forward validation
- ✅ Minimum trade constraint
- ✅ Max drawdown limiti
- ✅ Out-of-sample test

---

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun
3. Commit yapın
4. Push edin
5. Pull Request oluşturun

---

## 📄 Lisans

MIT License

---

## 🆘 Sorun Giderme

### Jesse backtest çalışmıyor

```bash
# Jesse kurulu mu?
jesse --version

# Veri var mı?
ls storage/

# Database setup
python setup_database.py
python import_data.py
```

### Optimizasyon çok yavaş

```python
# Config'de:
'use_multiprocessing': True
'num_workers': -1

# Popülasyon/jenerasyon azalt:
'population_size': 50
'num_generations': 20
```

### Memory hatası

```python
# Cache'i disable et
# fitness_evaluator.py'de cache_size sınırla
```

---

## 📚 Ek Kaynaklar

- [Jesse Docs](https://docs.jesse.trade)
- [Genetic Algorithm Detayları](GA_ALGORITHM_PSEUDOCODE.md)
- [Strateji Geliştirme Rehberi](https://docs.jesse.trade/docs/strategies)

---

**🎉 Başarılı optimizasyonlar dileriz!**
