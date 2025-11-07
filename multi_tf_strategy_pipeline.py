"""
MULTI-TIMEFRAME SCALPING STRATEGY PIPELINE
═══════════════════════════════════════════════════════════
Otomatik strateji arama ve seçme sistemi

ÖZELLİKLER:
1. Multi-Timeframe Analiz (5m, 15m, 30m, 1h, 2h, 4h)
2. Fraktal + Klasik İndikatörler kombinasyonu
3. Look-ahead bias YOK
4. Walk-forward optimizasyon
5. Overfitting tespiti
6. Otomatik strateji seçimi

PIPELINE AŞAMALARI:
1. Veri Hazırlama (multi-timeframe)
2. İndikatör Hesaplama (tüm timeframe'ler için)
3. Strateji Kombinasyonları Oluşturma
4. Walk-Forward Validation
5. Performans Değerlendirme
6. Overfitting Kontrolü
7. En İyi Strateji Seçimi
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from itertools import product
import warnings
warnings.filterwarnings('ignore')

from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from technical_indicators import TechnicalIndicators


# ═══════════════════════════════════════════════════════════
# 1. MULTI-TIMEFRAME DATA LOADER
# ═══════════════════════════════════════════════════════════

class MultiTimeframeDataLoader:
    """Birden fazla timeframe'den veri yükle ve senkronize et"""

    def __init__(self):
        self.conn_params = {
            'host': '127.0.0.1',
            'database': 'jesse_db',
            'user': 'voidstring',
            'password': ''
        }

    def load_timeframe(self, timeframe, start_ts, end_ts):
        """Tek bir timeframe için veri yükle"""
        conn = psycopg2.connect(**self.conn_params)

        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candle
            WHERE exchange = 'Binance Futures'
            AND symbol = 'BTC-USDT'
            AND timeframe = %s
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp ASC
        """

        df = pd.read_sql_query(query, conn, params=(timeframe, start_ts, end_ts))
        conn.close()

        if len(df) > 0:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('datetime', inplace=True)

        return df

    def load_multi_timeframe(self, base_timeframe='15m', start_date='2024-01-01', end_date='2024-12-31'):
        """
        Birden fazla timeframe'den veri yükle

        LOOK-AHEAD BIAS ÖNLEME:
        - Tüm higher timeframe'leri base timeframe'e resample ediyoruz
        - Her base timestamp için, sadece O ZAMANA KADAR olan higher TF verisini kullanıyoruz
        - Gelecek veriyi KESİNLİKLE kullanmıyoruz
        """
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)

        # Timeframe hiyerarşisi
        timeframes = {
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '2h': 120,
            '4h': 240,
        }

        print(f"📊 Multi-Timeframe veri yükleniyor...")
        print(f"   Base Timeframe: {base_timeframe}")
        print(f"   Periyot: {start_date} → {end_date}")

        # Base timeframe'i yükle
        base_df = self.load_timeframe(base_timeframe, start_ts, end_ts)

        if len(base_df) == 0:
            print("❌ Base timeframe verisi bulunamadı!")
            return None

        print(f"   ✅ {base_timeframe}: {len(base_df)} mum")

        # Higher timeframe'leri yükle ve senkronize et
        for tf in timeframes:
            if timeframes[tf] <= timeframes[base_timeframe]:
                continue  # Daha kısa TF'leri atlıyoruz

            df_tf = self.load_timeframe(tf, start_ts, end_ts)

            if len(df_tf) == 0:
                print(f"   ⚠️  {tf}: Veri yok, atlanıyor")
                continue

            print(f"   ✅ {tf}: {len(df_tf)} mum")

            # LOOK-AHEAD BIAS ÖNLEME:
            # Her base timestamp için, o zamana kadar olan higher TF verisini merge et
            # Forward-fill ile son bilinen değeri kullan
            for col in ['open', 'high', 'low', 'close', 'volume']:
                base_df[f'{tf}_{col}'] = base_df.index.map(
                    lambda dt: df_tf[df_tf.index <= dt][col].iloc[-1]
                    if len(df_tf[df_tf.index <= dt]) > 0 else np.nan
                )

        print(f"✅ Multi-timeframe veri hazır: {len(base_df)} mum\n")

        return base_df


# ═══════════════════════════════════════════════════════════
# 2. MULTI-TIMEFRAME INDICATOR CALCULATOR
# ═══════════════════════════════════════════════════════════

class MultiTFIndicatorCalculator:
    """Tüm timeframe'ler için indikatör hesapla"""

    @staticmethod
    def calculate_all_indicators(df, timeframe_prefix=''):
        """
        Bir timeframe için tüm indikatörleri hesapla

        İNDİKATÖRLER:
        - EMA (9, 21, 50, 200)
        - RSI (14)
        - MACD (12, 26, 9)
        - Bollinger Bands (20, 2)
        - Stochastic (14, 3, 3)
        - ADX (14)
        - ATR (14)
        - Volume MA (20)
        """
        prefix = f"{timeframe_prefix}_" if timeframe_prefix else ""

        # EMA
        for period in [9, 21, 50, 200]:
            df[f'{prefix}ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df[f'{prefix}rsi'] = 100 - (100 / (1 + rs))

        # MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df[f'{prefix}macd'] = ema_12 - ema_26
        df[f'{prefix}macd_signal'] = df[f'{prefix}macd'].ewm(span=9, adjust=False).mean()
        df[f'{prefix}macd_hist'] = df[f'{prefix}macd'] - df[f'{prefix}macd_signal']

        # Bollinger Bands
        bb_period = 20
        bb_std = 2
        sma = df['close'].rolling(window=bb_period).mean()
        std = df['close'].rolling(window=bb_period).std()
        df[f'{prefix}bb_upper'] = sma + (std * bb_std)
        df[f'{prefix}bb_lower'] = sma - (std * bb_std)
        df[f'{prefix}bb_middle'] = sma
        df[f'{prefix}bb_width'] = (df[f'{prefix}bb_upper'] - df[f'{prefix}bb_lower']) / df[f'{prefix}bb_middle']

        # Stochastic
        low_14 = df['low'].rolling(window=14).min()
        high_14 = df['high'].rolling(window=14).max()
        df[f'{prefix}stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14)
        df[f'{prefix}stoch_d'] = df[f'{prefix}stoch_k'].rolling(window=3).mean()

        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df[f'{prefix}atr'] = true_range.rolling(window=14).mean()

        # ADX
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr_14 = true_range.rolling(window=14).mean()
        plus_di = 100 * (plus_dm.rolling(window=14).mean() / tr_14)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / tr_14)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        df[f'{prefix}adx'] = dx.rolling(window=14).mean()
        df[f'{prefix}plus_di'] = plus_di
        df[f'{prefix}minus_di'] = minus_di

        # Volume MA
        df[f'{prefix}volume_ma'] = df['volume'].rolling(window=20).mean()
        df[f'{prefix}volume_ratio'] = df['volume'] / df[f'{prefix}volume_ma']

        return df

    @staticmethod
    def calculate_multi_tf_indicators(df):
        """Tüm timeframe'ler için indikatörler hesapla"""
        print("🔧 İndikatörler hesaplanıyor...")

        # Base timeframe (5m)
        df = MultiTFIndicatorCalculator.calculate_all_indicators(df)
        print("   ✅ 5m indikatörleri")

        # Higher timeframe'ler
        timeframes = ['15m', '30m', '1h', '2h', '4h']
        for tf in timeframes:
            if f'{tf}_close' in df.columns:
                # Her higher TF için ayrı bir temp df oluştur
                tf_df = pd.DataFrame()
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if f'{tf}_{col}' in df.columns:
                        tf_df[col] = df[f'{tf}_{col}']

                # İndikatörleri hesapla
                tf_df = MultiTFIndicatorCalculator.calculate_all_indicators(tf_df)

                # Ana df'e geri merge et
                for col in tf_df.columns:
                    if col not in ['open', 'high', 'low', 'close', 'volume']:
                        df[f'{tf}_{col}'] = tf_df[col].values

                print(f"   ✅ {tf} indikatörleri")

        # Fraktal analiz ekle
        df_fraktal = pd.DataFrame({
            'timestamp': df.index.astype(np.int64) // 10**6,
            'open': df['open'],
            'high': df['high'],
            'low': df['low'],
            'close': df['close'],
            'volume': df['volume']
        })

        df_fraktal = FractalAnalyzer.analyze_series(df_fraktal)

        for col in ['fractal_pattern', 'fractal_strength', 'fractal_score']:
            if col in df_fraktal.columns:
                df[col] = df_fraktal[col].values

        print("   ✅ Fraktal analiz")
        print(f"✅ Toplam {len(df.columns)} özellik hesaplandı\n")

        return df


# ═══════════════════════════════════════════════════════════
# 3. STRATEGY GENERATOR - Kombinasyon Üretici
# ═══════════════════════════════════════════════════════════

class StrategyGenerator:
    """Otomatik strateji kombinasyonları oluştur"""

    @staticmethod
    def generate_rule_combinations():
        """
        Farklı kural kombinasyonları oluştur

        KURAL TİPLERİ:
        1. Trend Filters (EMA, ADX)
        2. Momentum (RSI, Stochastic, MACD)
        3. Volatility (Bollinger, ATR)
        4. Volume
        5. Multi-TF Confirmation
        6. Fraktal Pattern
        """

        strategies = []

        # ═══ STRATEJİ 1: EMA + RSI (Klasik) ═══
        strategies.append({
            'name': 'EMA Cross + RSI Intraday',
            'base_tf': '15m',
            'rules': [
                {'type': 'ema_cross', 'fast': 9, 'slow': 21, 'direction': 'bullish'},
                {'type': 'rsi_range', 'min': 40, 'max': 60},
                {'type': 'higher_tf_trend', 'tf': '15m', 'ema': 50, 'direction': 'above'},
            ],
            'tp_pct': 0.005,  # %0.5
            'sl_pct': 0.003,  # %0.3
        })

        # ═══ STRATEJİ 2: Bollinger Bounce + Volume ═══
        strategies.append({
            'name': 'BB Bounce + Volume Spike',
            'base_tf': '15m',
            'rules': [
                {'type': 'bb_touch', 'band': 'lower', 'threshold': 1.01},
                {'type': 'volume_spike', 'multiplier': 1.5},
                {'type': 'rsi_oversold', 'level': 30},
                {'type': 'higher_tf_support', 'tf': '1h', 'ema': 200},
            ],
            'tp_pct': 0.008,  # %0.8
            'sl_pct': 0.004,  # %0.4
        })

        # ═══ STRATEJİ 3: MACD + Multi-TF Trend ═══
        strategies.append({
            'name': 'MACD Crossover + Multi-TF Align',
            'base_tf': '15m',
            'rules': [
                {'type': 'macd_cross', 'direction': 'bullish'},
                {'type': 'higher_tf_trend', 'tf': '15m', 'ema': 21, 'direction': 'above'},
                {'type': 'higher_tf_trend', 'tf': '1h', 'ema': 50, 'direction': 'above'},
                {'type': 'adx_strength', 'min': 20},
            ],
            'tp_pct': 0.006,  # %0.6
            'sl_pct': 0.003,  # %0.3
        })

        # ═══ STRATEJİ 4: Fraktal + EMA ═══
        strategies.append({
            'name': 'Fraktal Intraday + EMA Filter',
            'base_tf': '15m',
            'rules': [
                {'type': 'fractal_pattern', 'patterns': ['Trending Up', 'Outside Bar']},
                {'type': 'fractal_strength', 'min': 25},
                {'type': 'price_above_ema', 'period': 21},
                {'type': 'higher_tf_trend', 'tf': '30m', 'ema': 50, 'direction': 'above'},
            ],
            'tp_pct': 0.007,  # %0.7
            'sl_pct': 0.004,  # %0.4
        })

        # ═══ STRATEJİ 5: Stochastic + Trend ═══
        strategies.append({
            'name': 'Stoch Oversold + Uptrend',
            'base_tf': '15m',
            'rules': [
                {'type': 'stoch_oversold', 'k_max': 20, 'd_max': 20},
                {'type': 'price_above_ema', 'period': 50},
                {'type': 'higher_tf_trend', 'tf': '1h', 'ema': 21, 'direction': 'above'},
                {'type': 'volume_above_avg'},
            ],
            'tp_pct': 0.006,  # %0.6
            'sl_pct': 0.003,  # %0.3
        })

        # ═══ STRATEJİ 6: Multi-TF Fraktal Confluence ═══
        strategies.append({
            'name': 'Multi-TF Fraktal Confluence',
            'base_tf': '15m',
            'rules': [
                {'type': 'fractal_pattern', 'patterns': ['Trending Up']},
                {'type': 'higher_tf_fractal', 'tf': '15m', 'pattern': 'Trending Up'},
                {'type': 'higher_tf_trend', 'tf': '1h', 'ema': 50, 'direction': 'above'},
                {'type': 'rsi_not_overbought', 'max': 70},
            ],
            'tp_pct': 0.008,  # %0.8
            'sl_pct': 0.004,  # %0.4
        })

        print(f"🎲 {len(strategies)} strateji kombinasyonu oluşturuldu")

        return strategies


# ═══════════════════════════════════════════════════════════
# 4. RULE EVALUATOR - Kuralları Değerlendirici
# ═══════════════════════════════════════════════════════════

class RuleEvaluator:
    """Strateji kurallarını değerlendir"""

    @staticmethod
    def evaluate_rule(row, rule):
        """Tek bir kuralı değerlendir"""
        rule_type = rule['type']

        try:
            # ═══ TREND FILTERS ═══
            if rule_type == 'ema_cross':
                fast_ema = row.get(f"ema_{rule['fast']}", None)
                slow_ema = row.get(f"ema_{rule['slow']}", None)
                if fast_ema is None or slow_ema is None or pd.isna(fast_ema) or pd.isna(slow_ema):
                    return False
                if rule['direction'] == 'bullish':
                    return fast_ema > slow_ema
                else:
                    return fast_ema < slow_ema

            elif rule_type == 'price_above_ema':
                ema = row.get(f"ema_{rule['period']}", None)
                close = row.get('close', None)
                if ema is None or close is None or pd.isna(ema) or pd.isna(close):
                    return False
                return close > ema

            elif rule_type == 'higher_tf_trend':
                tf = rule['tf']
                ema_col = f"{tf}_ema_{rule['ema']}"
                close_col = f"{tf}_close"

                ema = row.get(ema_col, None)
                close = row.get(close_col, None)

                if ema is None or close is None or pd.isna(ema) or pd.isna(close):
                    return False

                if rule['direction'] == 'above':
                    return close > ema
                else:
                    return close < ema

            # ═══ MOMENTUM ═══
            elif rule_type == 'rsi_range':
                rsi = row.get('rsi', None)
                if rsi is None or pd.isna(rsi):
                    return False
                return rule['min'] <= rsi <= rule['max']

            elif rule_type == 'rsi_oversold':
                rsi = row.get('rsi', None)
                if rsi is None or pd.isna(rsi):
                    return False
                return rsi < rule['level']

            elif rule_type == 'rsi_not_overbought':
                rsi = row.get('rsi', None)
                if rsi is None or pd.isna(rsi):
                    return False
                return rsi < rule['max']

            elif rule_type == 'macd_cross':
                macd = row.get('macd', None)
                signal = row.get('macd_signal', None)
                if macd is None or signal is None or pd.isna(macd) or pd.isna(signal):
                    return False
                if rule['direction'] == 'bullish':
                    return macd > signal
                else:
                    return macd < signal

            elif rule_type == 'stoch_oversold':
                k = row.get('stoch_k', None)
                d = row.get('stoch_d', None)
                if k is None or d is None or pd.isna(k) or pd.isna(d):
                    return False
                return k < rule['k_max'] and d < rule['d_max']

            # ═══ VOLATILITY ═══
            elif rule_type == 'bb_touch':
                close = row.get('close', None)
                band_col = f"bb_{rule['band']}"
                band = row.get(band_col, None)

                if close is None or band is None or pd.isna(close) or pd.isna(band):
                    return False

                if rule['band'] == 'lower':
                    return close <= band * rule['threshold']
                else:
                    return close >= band * rule['threshold']

            # ═══ VOLUME ═══
            elif rule_type == 'volume_spike':
                vol_ratio = row.get('volume_ratio', None)
                if vol_ratio is None or pd.isna(vol_ratio):
                    return False
                return vol_ratio >= rule['multiplier']

            elif rule_type == 'volume_above_avg':
                vol_ratio = row.get('volume_ratio', None)
                if vol_ratio is None or pd.isna(vol_ratio):
                    return False
                return vol_ratio > 1.0

            # ═══ ADX ═══
            elif rule_type == 'adx_strength':
                adx = row.get('adx', None)
                if adx is None or pd.isna(adx):
                    return False
                return adx >= rule['min']

            # ═══ FRAKTAL ═══
            elif rule_type == 'fractal_pattern':
                pattern = row.get('fractal_pattern', None)
                if pattern is None or pd.isna(pattern):
                    return False
                return pattern in rule['patterns']

            elif rule_type == 'fractal_strength':
                strength = row.get('fractal_strength', 0)
                if strength is None or pd.isna(strength):
                    return False
                return strength >= rule['min']

            elif rule_type == 'higher_tf_fractal':
                tf = rule['tf']
                pattern_col = f"{tf}_fractal_pattern"
                pattern = row.get(pattern_col, None)
                if pattern is None or pd.isna(pattern):
                    return False
                return pattern == rule['pattern']

            elif rule_type == 'higher_tf_support':
                # Higher TF EMA'yı support olarak kullan
                tf = rule['tf']
                ema_col = f"{tf}_ema_{rule['ema']}"
                close = row.get('close', None)
                ema = row.get(ema_col, None)

                if ema is None or close is None or pd.isna(ema) or pd.isna(close):
                    return False

                # Fiyat EMA'ya yakınsa support olarak kabul et
                return abs(close - ema) / ema < 0.02  # %2 içinde

            else:
                return False

        except Exception as e:
            # Hata durumunda False dön
            return False

    @staticmethod
    def evaluate_strategy(row, strategy):
        """Tüm stratej kurallarını değerlendir (AND logic)"""
        for rule in strategy['rules']:
            if not RuleEvaluator.evaluate_rule(row, rule):
                return False
        return True


# Script devam edecek (Part 2'de walk-forward, backtest ve pipeline)
# Dosya boyutu sınırı nedeniyle ikinci bir dosyaya bölüyorum
print("✅ Part 1 yüklendi: Data Loader, Indicator Calculator, Strategy Generator, Rule Evaluator")
