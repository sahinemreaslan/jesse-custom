# Paper Trading Guide
## Başarılı Strateji: Production'a Geçiş Rehberi

---

## 📦 Hazır Olan Dosyalar

### 1. Stratejiler
```
strategies/
├── FractalTrend10x.py          # ✅ Baseline (36.88% ROI validated)
└── FractalTrendAdaptive.py     # ✅ Dynamic features (paralel geliştirme)
```

### 2. Konfigürasyon
```
routes.py                        # ✅ Jesse routing config
paper_trading_config.py          # ✅ Paper trading settings
test_strategies.py               # ✅ Comparison test script
```

### 3. Dökümanlar
```
STRATEGY_EVOLUTION_ANALYSIS.md   # Stratejinin evrimi ve RL yol haritası
PAPER_TRADING_GUIDE.md          # Bu döküman
```

---

## 🚀 Hızlı Başlangıç

### Adım 1: Test Backtesti (Doğrulama)

```bash
cd /home/voidstring/Desktop/jesse_real
source ~/miniconda3/etc/profile.d/conda.sh
conda activate jesse_env

# Baseline test (10x Aggressive)
jesse backtest 2024-01-01 2024-10-31
```

**Beklenen Sonuç:**
```
ROI: ~22% (10 ay)
Max Drawdown: ~-2.95%
Win Rate: ~52%
Profit Factor: ~1.36
Trades: ~600
```

### Adım 2: Adaptive Test (Opsiyonel)

```bash
# routes.py'de adaptive strategy'yi uncomment et
nano routes.py

# İkinci satırı aktif et:
# ('Binance Futures', 'BTC-USDT', timeframes.MINUTE_15, 'FractalTrendAdaptive'),

# Test
jesse backtest 2024-01-01 2024-10-31
```

**Beklenen İyileştirme:**
- ROI: 25-30% (adaptif özelliklerden)
- Max DD: Daha düşük (drawdown protection)
- Volatil dönemlerde daha iyi (adaptive TP/SL)

### Adım 3: Paper Trading Başlat

```bash
# Jesse paper trading mode
jesse paper-trade

# Veya live-mode test (simülasyon)
jesse run
```

---

## 📊 İki Strateji Karşılaştırması

### FractalTrend10x (Baseline)

**Özellikler:**
- ✅ Simple, rule-based
- ✅ Kanıtlanmış (36.88% ROI, 22 ay)
- ✅ %100 explainable
- ✅ 0 liquidation
- ✅ Düşük risk

**Parametreler:**
```python
Leverage: 10x
Position: 5% capital
TP: 0.7%
SL: 0.35%
Trailing: 0.5% activation, 0.2% distance
```

**Entry Kuralları (3 rule):**
1. 15m Fractal signal (Trending Up or Outside Bar)
2. Fractal strength >= 50
3. 4h trend up (Price > EMA50)

**Ne Zaman Kullan:**
- ✅ İlk paper trading
- ✅ Güvenli ve test edilmiş strateji istiyorsan
- ✅ Basitlik öncelikliyse

---

### FractalTrendAdaptive (Dynamic)

**Özellikler:**
- ⚡ Adaptive TP/SL (volatility-based)
- ⚡ Drawdown protection (automatic risk reduction)
- ⚡ Performance-based adjustments
- ⚡ Market regime detection (trend/range)

**Dinamik Parametreler:**
```python
Base: Same as baseline

# But dynamically adjusted:
TP/SL: Volatilite'ye göre genişler/daralır
Position Size: Drawdown'a göre küçülür
Fractal Threshold: Market regime'e göre değişir
```

**4 Dinamik Özellik:**

**1. Volatility-Adaptive TP/SL**
```python
if ATR > baseline:
    TP = 0.7% * (ATR_ratio)  # Wider in high vol
    SL = 0.35% * (ATR_ratio)
else:
    TP = 0.7% * (ATR_ratio)  # Tighter in low vol
    SL = 0.35% * (ATR_ratio)

# Clamped: TP (0.4-1.5%), SL (0.2-0.8%)
```

**2. Drawdown-Based Position Sizing**
```python
if DD = 0%:      position = 100% (5%)
if DD = -1%:     position = 100% (5%)
if DD = -2%:     position = 90%  (4.5%)
if DD = -3%:     position = 70%  (3.5%)
if DD = -4%:     position = 50%  (2.5%)
if DD = -5%:     STOP TRADING
```

**3. Performance Adaptation**
```python
if Win Rate > 60%:  position *= 1.1  # Hot streak bonus
if Win Rate < 40%:  position *= 0.9  # Cold streak reduction
```

**4. Market Regime Detection**
```python
if ADX > 25 (TRENDING):
    TP *= 1.2       # Longer TP
    strength -= 5   # Less strict filter

if ADX < 20 (RANGING):
    TP *= 0.8       # Shorter TP
    strength += 10  # More strict filter
```

**Ne Zaman Kullan:**
- ⚡ Baseline paper trading'de başarılı olduktan SONRA
- ⚡ Daha yüksek ROI hedefiyorsan
- ⚡ Market koşullarına adaptive olmasını istiyorsan
- ⚡ Drawdown riski azaltmak istiyorsan

---

## 📈 Performans Beklentileri

### 10 Aylık (2024 Jan-Oct)

| Metrik | Baseline | Adaptive | Hedef |
|--------|----------|----------|-------|
| **ROI** | 22.10% | 25-30% | >20% |
| **Max DD** | -2.95% | -2.5% | <-5% |
| **Win Rate** | 52.2% | 53-55% | >50% |
| **PF** | 1.45 | 1.50+ | >1.3 |
| **Trades** | 624 | 600-650 | ~600 |
| **Sharpe** | ~1.5 | ~1.8 | >1.2 |

### Aylık Breakdown (Expected)

| Month | Baseline ROI | Adaptive ROI | Notes |
|-------|-------------|--------------|-------|
| Month 1 | ~2% | ~2.5% | Learning period |
| Month 2 | ~2% | ~2.5% | Stabilization |
| Month 3-10 | ~2.3% | ~3% | Full performance |

---

## ⚙️ Konfigürasyon Ayarları

### Jesse Config (`config.py`)

```python
# Backtest settings
config = {
    'starting_balance': 10000,
    'fee': 0.0004,  # 0.04% Binance Futures
    'type': 'futures',
    'futures_leverage': 10,
    'futures_leverage_mode': 'cross',
}
```

### Routes (`routes.py`)

```python
from jesse.enums import timeframes

routes = [
    ('Binance Futures', 'BTC-USDT', timeframes.MINUTE_15, 'FractalTrend10x'),
]

extra_candles = [
    ('Binance Futures', 'BTC-USDT', timeframes.HOUR_4),  # For trend filter
]
```

---

## 🧪 Test ve Validasyon

### Test 1: Quick Backtest (1 month)

```bash
jesse backtest 2024-10-01 2024-10-31
```

Beklenen: ~2% ROI, 60-80 trade

### Test 2: Full Backtest (10 months)

```bash
jesse backtest 2024-01-01 2024-10-31
```

Beklenen: ~22% ROI, 600+ trade

### Test 3: Long Period (22 months)

```bash
jesse backtest 2023-01-01 2024-10-31
```

Beklenen: ~37% ROI, 800+ trade

### Test 4: Walk-Forward

```bash
# Q1
jesse backtest 2024-01-01 2024-03-31

# Q2
jesse backtest 2024-04-01 2024-06-30

# Q3
jesse backtest 2024-07-01 2024-09-30

# Q4
jesse backtest 2024-10-01 2024-10-31
```

Tutarlılık kontrolü: Her quarter pozitif olmalı

---

## 🎯 Paper Trading Plan

### Week 1-2: Baseline Monitoring

**Hedef:** Baseline'ın paper trading'de backtest sonuçlarını reproduce etmesi

**Yapılacaklar:**
- ✅ Her gün performance check
- ✅ Trade log kaydet
- ✅ Slippage ve komisyon gerçek mi kontrol et
- ✅ TP/SL düzgün tetikleniyor mu?

**Başarı Kriterleri:**
- ROI ~4% (2 hafta)
- DD < 2%
- 100-120 trade
- Win rate ~52%

### Week 3-4: Adaptive Testing

**Hedef:** Adaptive'in baseline'dan daha iyi perform etmesi

**Yapılacaklar:**
- ✅ Adaptive strategy'yi aktif et
- ✅ Dynamic features log'larını incele
- ✅ Volatility adaptation çalışıyor mu?
- ✅ Drawdown protection tetiklendi mi?

**Başarı Kriterleri:**
- ROI > Baseline
- DD < Baseline
- Features logically adapting

### Week 5-8: Decision Point

**Seçenekler:**

**A. Baseline Başarılı:**
```
✅ Baseline ile live'a geç
✅ Adaptive'i paralel geliştirmeye devam et
✅ Minimum risk, kanıtlanmış strateji
```

**B. Adaptive Daha İyi:**
```
⚡ Adaptive ile live'a geç
⚡ %25 daha yüksek ROI potential
⚡ Drawdown protection eklentisi
```

**C. İkisi de Kötü:**
```
❌ Live'a geçme
❌ Stratejide problem var, debug et
❌ Backtest vs paper trading farkını analiz et
```

---

## 📊 Monitoring ve Metrics

### Günlük Kontrol

```bash
# Jesse dashboard
jesse dashboard

# Veya manuel log check
tail -f storage/logs/paper-trade.log
```

**Günlük Track Edilecekler:**
- Daily ROI
- Number of trades
- Open positions
- Current DD
- Today's PnL

### Haftalık Review

**Metrics:**
```
Week 1 Performance:
  - ROI: X%
  - Trades: X
  - Win Rate: X%
  - Max DD: X%
  - Avg Trade: $X
  - Profit Factor: X
```

**Questions:**
- Backtest beklentileri ile uyumlu mu?
- Slippage impact ne kadar?
- Commission gerçek mi?
- TP/SL düzgün execute oluyor mu?

---

## ⚠️ Risk Management Rules

### Position Limits

```python
Max Position: 50% exposure (5% * 10x)
Max Leverage: 10x
Max Daily Trades: 20
Max Open Positions: 1
```

### Stop Conditions

```python
# Daily stops
if daily_loss < -2%:
    STOP_TRADING_TODAY

# Weekly stops
if weekly_loss < -5%:
    STOP_TRADING_THIS_WEEK

# Drawdown stops
if drawdown < -5%:
    STOP_ALL_TRADING
    REVIEW_STRATEGY

# Consecutive losses
if consecutive_losses >= 5:
    REDUCE_POSITION_SIZE_50%

# Liquidation
if liquidation_occurred:
    IMMEDIATE_STOP
    REVIEW_LEVERAGE
```

---

## 🔧 Troubleshooting

### Problem 1: ROI Paper'da Düşük

**Sebep:** Slippage, komisyon, execution delay

**Çözüm:**
```python
# TP/SL'yi biraz genişlet
tp_percent = 0.008  # 0.7% → 0.8%
sl_percent = 0.004  # 0.35% → 0.4%
```

### Problem 2: Çok Az Trade

**Sebep:** Fractal strength too strict

**Çözüm:**
```python
min_fractal_strength = 45  # 50 → 45
```

### Problem 3: Drawdown Fazla

**Sebep:** SL çok geniş veya consecutive losses

**Çözüm:**
```python
# SL sıkılaştır
sl_percent = 0.003  # 0.35% → 0.3%

# Veya adaptive drawdown protection aktif et
use_drawdown_protection = True
```

### Problem 4: Liquidation

**Sebep:** ⚠️⚠️ Kritik! Leverage çok yüksek

**Çözüm:**
```python
leverage = 5  # 10x → 5x
# Stratejiyi review et
# Paper trading'i durdur
```

---

## 🚦 Live Trading'e Geçiş Kriterleri

### Must-Have (Zorunlu)

- ✅ Paper trading 2+ ay başarılı
- ✅ ROI >= 15% (2 ay)
- ✅ Max DD < 5%
- ✅ 100+ trade
- ✅ Win rate ~52%
- ✅ Profit factor > 1.3
- ✅ 0 liquidation
- ✅ Tutarlı haftalık performance

### Nice-to-Have (İdeal)

- ⚡ Adaptive outperforms baseline
- ⚡ Sharpe ratio > 1.5
- ⚡ Drawdown recovery hızlı
- ⚡ Multiple market conditions tested

---

## 📝 Next Steps Checklist

### Şimdi (Bugün)

- [ ] `jesse backtest 2024-01-01 2024-10-31` çalıştır
- [ ] Sonuçları doğrula (~22% ROI)
- [ ] Adaptive test et (uncomment routes.py)
- [ ] İki stratejiyi karşılaştır

### Hafta 1-2 (Baseline Paper Trading)

- [ ] `jesse paper-trade` başlat
- [ ] Günlük performance tracking kur
- [ ] Trade log'larını incele
- [ ] Backtest vs paper farkını analiz et

### Hafta 3-4 (Adaptive Test)

- [ ] Adaptive strategy'yi aktif et
- [ ] Dynamic features performansını track et
- [ ] Baseline ile compare et
- [ ] En iyi stratejiyi seç

### Hafta 5-8 (Decision)

- [ ] 2 aylık performance review
- [ ] Live trading'e geçiş kriterlerini kontrol et
- [ ] Risk management kurallarını finalize et
- [ ] Live trading plan hazırla

### 3+ Ay (Live Trading)

- [ ] Küçük capital ile başla ($1000)
- [ ] 5x leverage (conservative)
- [ ] 1 ay test
- [ ] Gradual scale-up
- [ ] Full capital ($10K+)
- [ ] 10x leverage
- [ ] Continuous monitoring

---

## 📞 Support ve Resources

### Dökümanlar

- `STRATEGY_EVOLUTION_ANALYSIS.md`: Stratejinin evrimi ve RL roadmap
- `paper_trading_config.py`: Detaylı konfigürasyon ayarları
- `test_strategies.py`: Automated comparison script

### Jesse Documentation

- https://docs.jesse.trade
- https://forum.jesse.trade
- https://github.com/jesse-ai/jesse

### Monitoring

```bash
# Performance dashboard
jesse dashboard

# Live logs
tail -f storage/logs/paper-trade.log

# Error logs
tail -f storage/logs/error.log
```

---

## 🎉 Başarı Hikayesi

```
Initial Problem: -11.18% ROI (failed intraday adaptation)
                      ↓
Multi-TF Pipeline: +0.05% ROI (too complex)
                      ↓
Simplification: +9.44% ROI (4h filter)
                      ↓
Leverage: +22.10% ROI (10x)
                      ↓
Validation: +36.88% ROI (22 months)
                      ↓
Paper Trading: READY ✅
                      ↓
Adaptive Features: IN PROGRESS ⚡
                      ↓
Live Trading: SOON 🚀
```

**Timeline:**
- Week 1-2: Development → Done ✅
- Week 3-4: Backtesting → Done ✅
- Week 5-6: Validation → Done ✅
- **Week 7-8: Paper Trading → Current** 📍
- Week 9-16: Live (minimal)
- Week 17+: Live (full)

**Target ROI:**
- Paper Trading: 15-20% (2 months)
- Live Trading: 20-30% (annualized)

---

**Good Luck! 🚀**

*Remember: Paper trading başarısı = Live trading güveni*

*Be patient, track metrics, follow risk rules!*
