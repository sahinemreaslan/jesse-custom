# 🧬 Genetik Algoritma - Detaylı Pseudocode

Bu doküman, sistemin kalbini oluşturan **Genetik Algoritma**'nın detaylı çalışma prensibini açıklar.

---

## 📊 Genel Bakış

Genetik Algoritma (GA), doğal seçilim ve evrim prensiplerini taklit eden bir optimizasyon algoritmasıdır.

### Temel Kavramlar

- **Kromozom**: Bir parametre seti (örn: {fast_ma: 20, slow_ma: 50, rsi_period: 14})
- **Gen**: Tek bir parametre (örn: fast_ma = 20)
- **Birey**: Kromozom + fitness skoru
- **Popülasyon**: Bireyler topluluğu (örn: 100 farklı parametre seti)
- **Fitness**: Bireyin başarı skoru (Sharpe ratio, return, vb.)
- **Jenerasyon**: Bir evrim döngüsü

---

## 🔄 Ana Algoritma Akışı

```
┌─────────────────────────────────────┐
│ 1. BAŞLATMA (Initialization)       │
│    - Rastgele popülasyon oluştur   │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 2. DEĞERLENDİRME (Evaluation)      │
│    - Her bireyin fitness'ini hesapla│
│    - Jesse backtest çalıştır       │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 3. DURDURMA KONTROLÜ               │
│    - Max jenerasyon sayısına ulaşıldı mı?│
└─────────────┬───────────┬───────────┘
              │ EVET      │ HAYIR
              ▼           ▼
         ┌────────┐   ┌─────────────────────────────┐
         │ BİTİR  │   │ 4. SEÇİLİM (Selection)      │
         │        │   │    - En iyi bireyleri seç   │
         └────────┘   └─────────────┬───────────────┘
                                    │
                                    ▼
                      ┌─────────────────────────────┐
                      │ 5. ÇAPRAZLAMA (Crossover)   │
                      │    - Ebeveynleri karıştır   │
                      └─────────────┬───────────────┘
                                    │
                                    ▼
                      ┌─────────────────────────────┐
                      │ 6. MUTASYON (Mutation)      │
                      │    - Rastgele değişiklikler │
                      └─────────────┬───────────────┘
                                    │
                                    ▼
                      ┌─────────────────────────────┐
                      │ 7. ELİTİZM (Elitism)        │
                      │    - En iyileri koru        │
                      └─────────────┬───────────────┘
                                    │
                                    │
                                    └──────► 2. DEĞERLENDİRME'ye dön
```

---

## 1️⃣ BAŞLATMA (Initialization)

### Pseudocode

```
FUNCTION initialize_population(population_size, parameter_space):
    population = []

    FOR i = 1 TO population_size:
        chromosome = {}

        FOR EACH parameter IN parameter_space:
            IF parameter.type == INTEGER:
                value = RANDOM_INTEGER(parameter.min, parameter.max)
            ELSE IF parameter.type == FLOAT:
                value = RANDOM_FLOAT(parameter.min, parameter.max)
            ELSE IF parameter.type == BOOLEAN:
                value = RANDOM_BOOLEAN()

            chromosome[parameter.name] = value
        END FOR

        individual = Individual(chromosome=chromosome, fitness=-999999)
        population.append(individual)
    END FOR

    RETURN population
END FUNCTION
```

### Örnek

```python
# Parametre alanı:
# - fast_ma: [5, 50]
# - slow_ma: [50, 200]
# - rsi_period: [7, 28]

# Başlangıç popülasyonu (5 birey örneği):
population = [
    Individual({fast_ma: 23, slow_ma: 120, rsi_period: 14}, fitness=-999999),
    Individual({fast_ma: 18, slow_ma: 180, rsi_period: 21}, fitness=-999999),
    Individual({fast_ma: 35, slow_ma: 90, rsi_period: 10}, fitness=-999999),
    Individual({fast_ma: 12, slow_ma: 150, rsi_period: 25}, fitness=-999999),
    Individual({fast_ma: 42, slow_ma: 75, rsi_period: 18}, fitness=-999999),
]
```

---

## 2️⃣ DEĞERLENDİRME (Fitness Evaluation)

### Pseudocode

```
FUNCTION evaluate_population(population, fitness_evaluator):
    FOR EACH individual IN population:
        # Backtest çalıştır
        metrics = fitness_evaluator.run_backtest(individual.chromosome)

        # Kısıtlamaları kontrol et
        IF metrics.total_trades < MIN_TRADES:
            individual.fitness = -999999  # Çok kötü fitness
            CONTINUE
        END IF

        IF metrics.max_drawdown > MAX_DRAWDOWN_THRESHOLD:
            individual.fitness = -999999
            CONTINUE
        END IF

        IF metrics.win_rate < MIN_WIN_RATE:
            individual.fitness = -999999
            CONTINUE
        END IF

        # Fitness hesapla
        IF fitness_metric == "sharpe_ratio":
            individual.fitness = metrics.sharpe_ratio
        ELSE IF fitness_metric == "total_return":
            individual.fitness = metrics.total_return
        ELSE IF fitness_metric == "composite":
            individual.fitness = CALCULATE_COMPOSITE_FITNESS(metrics)
        END IF
    END FOR

    RETURN population
END FUNCTION
```

### Fitness Hesaplama

#### Sharpe Ratio

```
sharpe_ratio = (ortalama_getiri - risksiz_oran) / volatilite

# Örnek:
# Ortalama günlük getiri: 0.002 (0.2%)
# Volatilite: 0.015
# Risksiz oran: 0.0

sharpe = 0.002 / 0.015 = 0.133
sharpe_yıllık = sharpe * sqrt(365) = 2.54
```

#### Composite Fitness

```
FUNCTION calculate_composite_fitness(metrics):
    # Normalize et (0-1 arası)
    norm_sharpe = CLIP(metrics.sharpe / 3.0, 0, 1)
    norm_return = CLIP(metrics.total_return, 0, 1)
    norm_dd = CLIP(1 - (metrics.max_drawdown / 0.25), 0, 1)  # Düşük DD iyi
    norm_wr = metrics.win_rate

    # Ağırlıklı toplam
    fitness = (
        0.4 * norm_sharpe +
        0.3 * norm_return +
        0.2 * norm_dd +
        0.1 * norm_wr
    )

    RETURN fitness
END FUNCTION
```

---

## 3️⃣ SEÇİLİM (Selection) - Tournament Selection

### Pseudocode

```
FUNCTION tournament_selection(population, tournament_size):
    # Rastgele tournament_size kadar birey seç
    tournament = RANDOM_SAMPLE(population, tournament_size)

    # En yüksek fitness'e sahip olanı bul
    winner = tournament[0]
    FOR EACH individual IN tournament:
        IF individual.fitness > winner.fitness:
            winner = individual
        END IF
    END FOR

    RETURN winner
END FUNCTION
```

### Örnek

```python
# Popülasyon:
[
    Individual(..., fitness=2.3),
    Individual(..., fitness=1.8),
    Individual(..., fitness=3.1),  # ← En iyi
    Individual(..., fitness=0.5),
    Individual(..., fitness=2.7),
]

# Tournament size = 3
# Rastgele 3 birey seç: [fitness=1.8, fitness=3.1, fitness=0.5]
# En yüksek fitness: 3.1
# Kazanan: Individual(..., fitness=3.1)
```

---

## 4️⃣ ÇAPRAZLAMA (Crossover) - Uniform Crossover

### Pseudocode

```
FUNCTION uniform_crossover(parent1, parent2):
    child1 = {}
    child2 = {}

    FOR EACH gene_name IN parameter_names:
        IF RANDOM() < 0.5:
            # Çocuk 1, ebeveyn 1'den alır
            # Çocuk 2, ebeveyn 2'den alır
            child1[gene_name] = parent1[gene_name]
            child2[gene_name] = parent2[gene_name]
        ELSE:
            # Çapraz
            child1[gene_name] = parent2[gene_name]
            child2[gene_name] = parent1[gene_name]
        END IF
    END FOR

    RETURN child1, child2
END FUNCTION
```

### Örnek

```python
# Ebeveynler:
parent1 = {fast_ma: 20, slow_ma: 100, rsi_period: 14}
parent2 = {fast_ma: 35, slow_ma: 150, rsi_period: 21}

# Uniform crossover (her gen için %50 şans):
# Gen 1 (fast_ma): Rastgele < 0.5 → Çaprazlama YOK
#   child1 = 20 (parent1'den)
#   child2 = 35 (parent2'den)

# Gen 2 (slow_ma): Rastgele >= 0.5 → Çaprazlama VAR
#   child1 = 150 (parent2'den)
#   child2 = 100 (parent1'den)

# Gen 3 (rsi_period): Rastgele < 0.5 → Çaprazlama YOK
#   child1 = 14 (parent1'den)
#   child2 = 21 (parent2'den)

# Sonuç:
child1 = {fast_ma: 20, slow_ma: 150, rsi_period: 14}
child2 = {fast_ma: 35, slow_ma: 100, rsi_period: 21}
```

---

## 5️⃣ MUTASYON (Mutation) - Gaussian Mutation

### Pseudocode

```
FUNCTION mutate(chromosome, mutation_sigma):
    mutated = {}

    FOR EACH gene_name IN chromosome:
        parameter = parameter_space[gene_name]
        value = chromosome[gene_name]

        IF parameter.type == INTEGER:
            # Gaussian mutasyon
            range_size = parameter.max - parameter.min
            delta = GAUSSIAN(mean=0, std=range_size * mutation_sigma)
            new_value = value + delta
            new_value = CLIP(new_value, parameter.min, parameter.max)
            mutated[gene_name] = ROUND(new_value)

        ELSE IF parameter.type == FLOAT:
            range_size = parameter.max - parameter.min
            delta = GAUSSIAN(mean=0, std=range_size * mutation_sigma)
            new_value = value + delta
            mutated[gene_name] = CLIP(new_value, parameter.min, parameter.max)

        ELSE IF parameter.type == BOOLEAN:
            IF RANDOM() < 0.5:
                mutated[gene_name] = NOT value
            ELSE:
                mutated[gene_name] = value
            END IF
        END IF
    END FOR

    RETURN mutated
END FUNCTION
```

### Örnek

```python
# Orijinal kromozom:
chromosome = {fast_ma: 20, slow_ma: 100, rsi_period: 14}

# Mutasyon (sigma = 0.1):
# fast_ma: range = 45 (50-5), delta = GAUSSIAN(0, 4.5) = +3
#   20 + 3 = 23

# slow_ma: range = 150, delta = GAUSSIAN(0, 15) = -8
#   100 - 8 = 92

# rsi_period: range = 21, delta = GAUSSIAN(0, 2.1) = +1
#   14 + 1 = 15

# Mutasyonlu kromozom:
mutated = {fast_ma: 23, slow_ma: 92, rsi_period: 15}
```

---

## 6️⃣ ELİTİZM (Elitism)

### Pseudocode

```
FUNCTION apply_elitism(current_population, new_population, elitism_count):
    # Mevcut popülasyonu fitness'e göre sırala
    sorted_pop = SORT(current_population, BY=fitness, DESCENDING)

    # En iyi N'i al
    elites = sorted_pop[0:elitism_count]

    # Yeni popülasyonun başına ekle
    final_population = elites + new_population[elitism_count:]

    RETURN final_population
END FUNCTION
```

### Örnek

```python
# Mevcut popülasyon (100 birey, en iyi 5'i):
current_best = [
    Individual(..., fitness=3.2),  # ← En iyi
    Individual(..., fitness=3.0),
    Individual(..., fitness=2.9),
    Individual(..., fitness=2.8),
    Individual(..., fitness=2.7),
]

# Yeni popülasyon (selection, crossover, mutation sonrası):
new_population = [95 yeni birey...]

# Elitism (count=5):
# En iyi 5'i yeni popülasyona ekle
final_population = current_best[:5] + new_population[:95]

# Sonuç: En iyi 5 birey direkt korundu, 95 birey yeni evrim sonucu
```

---

## 🔁 Tam Evrim Döngüsü

### Main GA Loop Pseudocode

```
FUNCTION run_genetic_algorithm(
    parameter_space,
    population_size,
    num_generations,
    crossover_prob,
    mutation_prob,
    mutation_sigma,
    tournament_size,
    elitism_count
):
    # 1. BAŞLATMA
    population = initialize_population(population_size, parameter_space)

    # 2. EVRIM DÖNGÜSÜ
    FOR generation = 0 TO num_generations - 1:
        # 2.1 Fitness değerlendirme
        population = evaluate_population(population, fitness_evaluator)

        # 2.2 İstatistikleri kaydet
        best_fitness = MAX(population.fitness)
        avg_fitness = AVERAGE(population.fitness)
        worst_fitness = MIN(population.fitness)

        PRINT "Jenerasyon", generation, ":"
        PRINT "  En İyi:", best_fitness
        PRINT "  Ortalama:", avg_fitness

        # 2.3 Son jenerasyon değilse, yeni jenerasyon oluştur
        IF generation < num_generations - 1:
            new_population = []

            # Elitism: En iyileri koru
            sorted_pop = SORT(population, BY=fitness, DESCENDING)
            elites = sorted_pop[0:elitism_count]
            new_population.extend(elites)

            # Selection + Crossover + Mutation ile geri kalanı oluştur
            WHILE LENGTH(new_population) < population_size:
                # Selection
                parent1 = tournament_selection(population, tournament_size)
                parent2 = tournament_selection(population, tournament_size)

                # Crossover
                IF RANDOM() < crossover_prob:
                    child1, child2 = uniform_crossover(parent1, parent2)
                ELSE:
                    child1 = COPY(parent1)
                    child2 = COPY(parent2)
                END IF

                # Mutation
                IF RANDOM() < mutation_prob:
                    child1 = mutate(child1, mutation_sigma)
                END IF
                IF RANDOM() < mutation_prob:
                    child2 = mutate(child2, mutation_sigma)
                END IF

                # Yeni popülasyona ekle
                new_population.append(Individual(child1))
                IF LENGTH(new_population) < population_size:
                    new_population.append(Individual(child2))
                END IF
            END WHILE

            population = new_population
        END IF
    END FOR

    # 3. En iyi bireyi döndür
    sorted_final = SORT(population, BY=fitness, DESCENDING)
    best_individual = sorted_final[0]

    RETURN best_individual
END FUNCTION
```

---

## 📊 Örnek Çalışma Senaryosu

### Senaryo Parametreleri

```
population_size = 10  # Basitlik için küçük
num_generations = 3
crossover_prob = 0.7
mutation_prob = 0.2
tournament_size = 3
elitism_count = 2

Parametre alanı:
  - fast_ma: [5, 50]
  - slow_ma: [50, 200]
```

### Jenerasyon 0 (Başlangıç)

```
Rastgele popülasyon oluştur:
[
    Individual({fast_ma: 23, slow_ma: 120}, fitness=?),
    Individual({fast_ma: 18, slow_ma: 180}, fitness=?),
    Individual({fast_ma: 35, slow_ma: 90}, fitness=?),
    Individual({fast_ma: 12, slow_ma: 150}, fitness=?),
    Individual({fast_ma: 42, slow_ma: 75}, fitness=?),
    Individual({fast_ma: 28, slow_ma: 110}, fitness=?),
    Individual({fast_ma: 15, slow_ma: 195}, fitness=?),
    Individual({fast_ma: 38, slow_ma: 135}, fitness=?),
    Individual({fast_ma: 20, slow_ma: 165}, fitness=?),
    Individual({fast_ma: 45, slow_ma: 85}, fitness=?),
]

Backtest çalıştır ve fitness hesapla:
[
    Individual({fast_ma: 23, slow_ma: 120}, fitness=1.8),
    Individual({fast_ma: 18, slow_ma: 180}, fitness=2.3),  ← En iyi
    Individual({fast_ma: 35, slow_ma: 90}, fitness=0.5),
    Individual({fast_ma: 12, slow_ma: 150}, fitness=1.2),
    Individual({fast_ma: 42, slow_ma: 75}, fitness=-0.3),
    Individual({fast_ma: 28, slow_ma: 110}, fitness=2.1),  ← 2. en iyi (elite)
    Individual({fast_ma: 15, slow_ma: 195}, fitness=0.9),
    Individual({fast_ma: 38, slow_ma: 135}, fitness=1.5),
    Individual({fast_ma: 20, slow_ma: 165}, fitness=1.0),
    Individual({fast_ma: 45, slow_ma: 85}, fitness=-0.5),
]

İstatistikler:
  En İyi: 2.3
  Ortalama: 1.05
  En Kötü: -0.5
```

### Jenerasyon 1

```
Elitism: En iyi 2'yi koru
  - {fast_ma: 18, slow_ma: 180, fitness: 2.3}
  - {fast_ma: 28, slow_ma: 110, fitness: 2.1}

Kalan 8 birey için:

1. Selection (Tournament)
   - Turnuva 1: [{fitness: 1.8}, {fitness: 0.5}, {fitness: 1.5}] → Kazanan: 1.8
   - Turnuva 2: [{fitness: 2.1}, {fitness: 0.9}, {fitness: -0.3}] → Kazanan: 2.1

2. Crossover (prob = 0.7, %70 şans)
   - RANDOM() = 0.45 < 0.7 → YAPILIR
   - parent1 = {fast_ma: 23, slow_ma: 120}
   - parent2 = {fast_ma: 28, slow_ma: 110}
   - child1 = {fast_ma: 23, slow_ma: 110}  # fast_ma parent1'den, slow_ma parent2'den
   - child2 = {fast_ma: 28, slow_ma: 120}

3. Mutation (prob = 0.2, %20 şans)
   - child1: RANDOM() = 0.15 < 0.2 → MUTAthe YAPILIR
     - fast_ma: 23 + GAUSSIAN(0, 4.5) = 23 + 2 = 25
     - slow_ma: 110 + GAUSSIAN(0, 15) = 110 - 5 = 105
     - mutated_child1 = {fast_ma: 25, slow_ma: 105}

   - child2: RANDOM() = 0.75 > 0.2 → MUTASYON YOK
     - child2 = {fast_ma: 28, slow_ma: 120}

... bu işlem 8 çocuk oluşana kadar devam eder ...

Yeni popülasyon (elites + çocuklar):
[
    Individual({fast_ma: 18, slow_ma: 180}, fitness=2.3),  # Elite
    Individual({fast_ma: 28, slow_ma: 110}, fitness=2.1),  # Elite
    Individual({fast_ma: 25, slow_ma: 105}, fitness=?),    # Yeni
    Individual({fast_ma: 28, slow_ma: 120}, fitness=?),    # Yeni
    ... 6 yeni çocuk daha ...
]

Backtest çalıştır:
[
    Individual({fast_ma: 18, slow_ma: 180}, fitness=2.3),
    Individual({fast_ma: 28, slow_ma: 110}, fitness=2.1),
    Individual({fast_ma: 25, slow_ma: 105}, fitness=2.4),  ← YENİ EN İYİ!
    ...
]

İstatistikler:
  En İyi: 2.4  (↑ İyileşme!)
  Ortalama: 1.45  (↑ İyileşme!)
```

### Jenerasyon 2

```
Elitism: En iyi 2'yi koru
  - {fast_ma: 25, slow_ma: 105, fitness: 2.4}  ← Yeni lider
  - {fast_ma: 18, slow_ma: 180, fitness: 2.3}

... aynı süreç devam eder ...

Sonuç:
  En İyi: 2.6
  Ortalama: 1.8
```

### Final Sonuç

```
En iyi birey (3 jenerasyon sonrası):
  Kromozom: {fast_ma: 22, slow_ma: 115}
  Fitness: 2.6
  Metrikler:
    - Total Return: 34.5%
    - Sharpe Ratio: 2.6
    - Max Drawdown: -6.2%
    - Win Rate: 61.3%
    - Trades: 87
```

---

## 🎯 Algoritma Karmaşıklığı

### Zaman Karmaşıklığı

```
T(n) = G * P * T_backtest

Burada:
  G = Jenerasyon sayısı (num_generations)
  P = Popülasyon büyüklüğü (population_size)
  T_backtest = Tek bir backtest süresi

Örnek:
  G = 50
  P = 100
  T_backtest = 5 saniye

  Toplam süre = 50 * 100 * 5 = 25,000 saniye = ~7 saat

Paralelleştirme ile (8 CPU):
  Toplam süre ≈ 25,000 / 8 = 3,125 saniye ≈ 52 dakika
```

### Uzay Karmaşıklığı

```
S(n) = P * C

Burada:
  P = Popülasyon büyüklüğü
  C = Kromozom boyutu (parametre sayısı)

Örnek:
  P = 100
  C = 6 parametre

  Bellek kullanımı ≈ 100 * 6 * 8 bytes = 4.8 KB (ihmal edilebilir)
```

---

## ⚡ Optimizasyon Teknikleri

### 1. Paralel Fitness Değerlendirmesi

```
FUNCTION evaluate_population_parallel(population, num_workers):
    # Popülasyonu chunk'lara böl
    chunks = SPLIT(population, num_workers)

    # Her worker bir chunk'ı işler
    results = []
    FOR EACH chunk IN chunks (PARALLEL):
        chunk_results = []
        FOR EACH individual IN chunk:
            fitness, metrics = evaluate(individual)
            individual.fitness = fitness
            individual.metrics = metrics
            chunk_results.append(individual)
        END FOR
        results.append(chunk_results)
    END FOR (WAIT FOR ALL)

    # Sonuçları birleştir
    evaluated_population = FLATTEN(results)

    RETURN evaluated_population
END FUNCTION
```

### 2. Fitness Cache

```
cache = {}

FUNCTION evaluate_with_cache(chromosome):
    key = HASH(chromosome)

    IF key IN cache:
        RETURN cache[key]  # Cache hit!
    ELSE:
        fitness, metrics = run_backtest(chromosome)
        cache[key] = (fitness, metrics)
        RETURN fitness, metrics
    END IF
END FUNCTION
```

### 3. Adaptive Mutation Rate

```
FUNCTION adaptive_mutation_rate(generation, num_generations):
    # İlk jenerasyonlarda yüksek mutasyon (keşif)
    # Son jenerasyonlarda düşük mutasyon (hassaslaştırma)

    progress = generation / num_generations
    mutation_rate = 0.3 * (1 - progress) + 0.1 * progress

    RETURN mutation_rate

# Örnek:
# Gen 0: 0.3 (yüksek)
# Gen 25: 0.2 (orta)
# Gen 50: 0.1 (düşük)
```

---

## 🔍 Debugging İpuçları

### Fitness'lerin İzlenmesi

```python
# Her jenerasyonda:
LOG "Gen", generation
LOG "  Best:", MAX(population.fitness)
LOG "  Avg:", AVERAGE(population.fitness)
LOG "  Std:", STD(population.fitness)

# Eğer:
# - Best değişmiyorsa → Mutation artır
# - Std çok düşükse → Diversity kaybedilmiş, popülasyonu reset et
# - Avg hızla artıyorsa → İyi gidiyor!
```

### Kromozom Dağılımı

```python
# Her parametre için histogram:
FOR EACH parameter IN parameter_space:
    values = [ind.chromosome[parameter.name] FOR ind IN population]
    PLOT_HISTOGRAM(values)

# Eğer tüm değerler bir noktada toplanmışsa → Premature convergence
```

---

## 📚 Ek Kaynaklar

- [Genetik Algoritmalar Teorisi](https://en.wikipedia.org/wiki/Genetic_algorithm)
- [Jesse Backtest Engine](https://docs.jesse.trade/docs/strategies/api.html)
- [Fitness Function Design](https://www.researchgate.net/publication/fitness_functions)

---

**🎯 Sistem bu algoritmayı kullanarak optimal trading stratejilerini keşfeder!**
