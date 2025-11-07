# 🧬 Jesse AI + Genetik Algoritma Optimizer

**Jesse Framework** tabanlı kripto trading sistemi + **Genetik Algoritma** ile strateji optimizasyonu.

---

## 🎯 Proje Özeti

Bu proje iki ana bileşenden oluşur:

### 1. **Jesse AI Trading Framework**
- Profesyonel backtesting motoru
- Teknik indikatör kütüphanesi
- Multi-timeframe analiz desteği
- PostgreSQL tabanlı veri yönetimi

### 2. **Genetik Algoritma Optimizer** ⭐ YENİ
- Strateji parametrelerini otomatik optimize eder
- Evrim prensiplerine dayalı akıllı arama
- Sharpe ratio, return, drawdown odaklı optimizasyon
- Paralel işlem desteği (8x hızlanma)

---

## 📊 Sistem Mimarisi

```
┌─────────────────────────────────────────────────┐
│          JESSE FRAMEWORK                        │
│  (Backtest Engine, Indicators, Data)            │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│     GENETIK ALGORITMA OPTIMIZER                 │
│                                                 │
│  📌 Parametre Arama Alanı Tanımlama            │
│  🧬 Rastgele Popülasyon Oluşturma              │
│  📊 Fitness Değerlendirme (Backtest)           │
│  ⚡ Evrim (Selection, Crossover, Mutation)     │
│  🏆 En İyi Parametreleri Bulma                 │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│      OPTIMIZE EDİLMİŞ STRATEJİ                  │
│  (En kârlı, en stabil parametreler)             │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Hızlı Başlangıç

### Kurulum

```bash
# Repo'yu clone et
git clone <repo-url>
cd jesse-custom

# Virtual environment oluştur (opsiyonel)
python3 -m venv venv
source venv/bin/activate

# Bağımlılıkları yükle
pip install jesse
pip install matplotlib seaborn pandas numpy

# Veritabanını kur
python setup_database.py

# Tarihsel veri indir
python import_data.py
```

### GA Optimizer Çalıştırma

```bash
# Genetik Algoritma ile optimizasyon başlat
python main_ga_optimizer.py
```

---

## 📚 Dokümantasyon

- 📖 [GA Optimizer Detaylı Rehber](GA_OPTIMIZER_README.md)
- 🧬 [Genetik Algoritma Pseudocode](GA_ALGORITHM_PSEUDOCODE.md)
- 🔗 [Jesse Docs](https://docs.jesse.trade)

---

## 📄 Lisans

MIT License

---

**🎯 Başarılı optimizasyonlar dileriz!**
