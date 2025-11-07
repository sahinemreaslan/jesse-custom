"""
TECHNICAL INDICATORS - Teknik Göstergeler
═══════════════════════════════════════════════════════════
Popüler trading göstergeleri (RSI, MACD, Bollinger, EMA vb)
═══════════════════════════════════════════════════════════
"""
import pandas as pd
import numpy as np


class TechnicalIndicators:
    """Teknik göstergeler sınıfı"""

    @staticmethod
    def RSI(df, period=14, column='close'):
        """Relative Strength Index"""
        delta = df[column].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def MACD(df, fast=12, slow=26, signal=9, column='close'):
        """Moving Average Convergence Divergence"""
        ema_fast = df[column].ewm(span=fast, adjust=False).mean()
        ema_slow = df[column].ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line

        return pd.DataFrame({
            'macd': macd,
            'signal': signal_line,
            'histogram': histogram
        })

    @staticmethod
    def BollingerBands(df, period=20, std_dev=2, column='close'):
        """Bollinger Bands"""
        sma = df[column].rolling(window=period).mean()
        std = df[column].rolling(window=period).std()

        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return pd.DataFrame({
            'bb_upper': upper,
            'bb_middle': sma,
            'bb_lower': lower,
            'bb_width': upper - lower
        })

    @staticmethod
    def EMA(df, period=20, column='close'):
        """Exponential Moving Average"""
        return df[column].ewm(span=period, adjust=False).mean()

    @staticmethod
    def SMA(df, period=20, column='close'):
        """Simple Moving Average"""
        return df[column].rolling(window=period).mean()

    @staticmethod
    def ATR(df, period=14):
        """Average True Range (volatilite)"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    @staticmethod
    def Stochastic(df, period=14, smooth_k=3, smooth_d=3):
        """Stochastic Oscillator"""
        low_min = df['low'].rolling(window=period).min()
        high_max = df['high'].rolling(window=period).max()

        k = 100 * ((df['close'] - low_min) / (high_max - low_min))
        k = k.rolling(window=smooth_k).mean()
        d = k.rolling(window=smooth_d).mean()

        return pd.DataFrame({
            'stoch_k': k,
            'stoch_d': d
        })

    @staticmethod
    def ADX(df, period=14):
        """Average Directional Index (trend gücü)"""
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr = TechnicalIndicators.ATR(df, period=1)

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / tr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / tr)

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return pd.DataFrame({
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di
        })

    @staticmethod
    def VolumeMA(df, period=20):
        """Volume Moving Average"""
        return df['volume'].rolling(window=period).mean()

    @staticmethod
    def VWAP(df):
        """Volume Weighted Average Price"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()

    @staticmethod
    def add_all_indicators(df):
        """Tüm göstergeleri ekle"""
        result = df.copy()

        # RSI
        result['rsi'] = TechnicalIndicators.RSI(df)

        # MACD
        macd_df = TechnicalIndicators.MACD(df)
        result = pd.concat([result, macd_df], axis=1)

        # Bollinger Bands
        bb_df = TechnicalIndicators.BollingerBands(df)
        result = pd.concat([result, bb_df], axis=1)

        # EMA
        result['ema_9'] = TechnicalIndicators.EMA(df, 9)
        result['ema_21'] = TechnicalIndicators.EMA(df, 21)
        result['ema_50'] = TechnicalIndicators.EMA(df, 50)

        # SMA
        result['sma_20'] = TechnicalIndicators.SMA(df, 20)
        result['sma_50'] = TechnicalIndicators.SMA(df, 50)

        # ATR
        result['atr'] = TechnicalIndicators.ATR(df)

        # Stochastic
        stoch_df = TechnicalIndicators.Stochastic(df)
        result = pd.concat([result, stoch_df], axis=1)

        # ADX
        adx_df = TechnicalIndicators.ADX(df)
        result = pd.concat([result, adx_df], axis=1)

        # Volume
        result['volume_ma'] = TechnicalIndicators.VolumeMA(df)
        result['vwap'] = TechnicalIndicators.VWAP(df)

        return result


if __name__ == '__main__':
    # Test
    print("Technical Indicators modülü hazır!")
    print("\nMevcut göstergeler:")
    print("  - RSI (Relative Strength Index)")
    print("  - MACD (Moving Average Convergence Divergence)")
    print("  - Bollinger Bands")
    print("  - EMA/SMA (Moving Averages)")
    print("  - ATR (Average True Range)")
    print("  - Stochastic Oscillator")
    print("  - ADX (Average Directional Index)")
    print("  - Volume indicators (MA, VWAP)")
