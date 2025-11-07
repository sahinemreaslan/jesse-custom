"""
DataHandler - Veri Yönetim Modülü

Sorumluluklar:
- Borsalardan tarihsel veri çekme (ccxt)
- Veriyi veritabanına kaydetme (SQLite/InfluxDB)
- Veriyi DataFrame olarak servis etme
- Canlı veri akışı (WebSocket - opsiyonel)

Author: GA Trading System
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import pandas as pd
import numpy as np
import ccxt
from pathlib import Path


class DataHandler:
    """
    Veri yönetimi ve servis sağlayıcı sınıf.

    Attributes:
        exchange: CCXT exchange instance
        db_path: Veritabanı dosya yolu
        symbol: Trading çifti (örn: 'BTC/USDT')
        timeframe: Zaman dilimi (örn: '1h', '15m')
    """

    def __init__(
        self,
        exchange_name: str = 'binance',
        db_path: str = 'data/historical/trading.db',
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True
    ):
        """
        DataHandler başlatıcı.

        Args:
            exchange_name: Borsa adı ('binance', 'bybit', vb.)
            db_path: SQLite veritabanı yolu
            api_key: API anahtarı (opsiyonel, public data için gerekli değil)
            api_secret: API secret (opsiyonel)
            testnet: Testnet kullanılacak mı?
        """
        self.exchange_name = exchange_name
        self.db_path = db_path
        self.testnet = testnet

        # Veritabanı dizinini oluştur
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Exchange bağlantısını başlat
        self.exchange = self._initialize_exchange(api_key, api_secret)

        # Veritabanını başlat
        self._initialize_database()

    def _initialize_exchange(
        self,
        api_key: Optional[str],
        api_secret: Optional[str]
    ) -> ccxt.Exchange:
        """
        CCXT exchange instance oluştur.

        Args:
            api_key: API anahtarı
            api_secret: API secret

        Returns:
            ccxt.Exchange: Exchange instance
        """
        exchange_class = getattr(ccxt, self.exchange_name)

        config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # spot veya future
            }
        }

        if api_key and api_secret:
            config['apiKey'] = api_key
            config['secret'] = api_secret

        if self.testnet and hasattr(exchange_class, 'testnet'):
            config['options']['testnet'] = True

        exchange = exchange_class(config)

        return exchange

    def _initialize_database(self) -> None:
        """SQLite veritabanını oluştur/başlat."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # OHLCV tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, timestamp)
            )
        ''')

        # İndeksler
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_timestamp
            ON ohlcv(symbol, timeframe, timestamp)
        ''')

        conn.commit()
        conn.close()

    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str = '1h',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Borsadan tarihsel OHLCV verisi çek.

        Args:
            symbol: Trading çifti (örn: 'BTC/USDT')
            timeframe: Zaman dilimi ('1m', '5m', '15m', '1h', '4h', '1d')
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi
            limit: Her seferde çekilecek maks. mum sayısı

        Returns:
            pd.DataFrame: OHLCV verisi [timestamp, open, high, low, close, volume]
        """
        # Tarih aralığını belirle
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now()

        # Timestamp'e çevir
        since = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)

        all_candles = []

        # Pagination ile tüm veriyi çek
        while since < end_ts:
            try:
                candles = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=limit
                )

                if not candles:
                    break

                all_candles.extend(candles)

                # Son mum timestamp'i
                since = candles[-1][0] + 1

                # Rate limit için bekleme
                self.exchange.sleep(self.exchange.rateLimit)

            except Exception as e:
                print(f"Veri çekme hatası: {e}")
                break

        # DataFrame'e çevir
        df = pd.DataFrame(
            all_candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )

        # Timestamp'i datetime'a çevir
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        # Duplicate'leri temizle
        df = df[~df.index.duplicated(keep='last')]

        return df

    def save_to_db(
        self,
        data: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> int:
        """
        OHLCV verisini veritabanına kaydet.

        Args:
            data: OHLCV DataFrame
            symbol: Trading çifti
            timeframe: Zaman dilimi

        Returns:
            int: Kaydedilen satır sayısı
        """
        conn = sqlite3.connect(self.db_path)

        # DataFrame'i hazırla
        df = data.copy()
        df.reset_index(inplace=True)

        # Timestamp'i integer'a çevir
        df['timestamp_int'] = (df['timestamp'].astype(np.int64) // 10**6)

        # Symbol ve timeframe ekle
        df['symbol'] = symbol
        df['timeframe'] = timeframe

        # Sütunları düzenle
        df = df[[
            'symbol', 'timeframe', 'timestamp_int',
            'open', 'high', 'low', 'close', 'volume'
        ]]

        df.columns = [
            'symbol', 'timeframe', 'timestamp',
            'open', 'high', 'low', 'close', 'volume'
        ]

        # Veritabanına kaydet (REPLACE ile duplicate'leri güncelle)
        inserted = 0
        for _, row in df.iterrows():
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO ohlcv
                    (symbol, timeframe, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', tuple(row))
                inserted += 1
            except Exception as e:
                print(f"Satır kaydetme hatası: {e}")

        conn.commit()
        conn.close()

        return inserted

    def get_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Veritabanından OHLCV verisi al.

        Args:
            symbol: Trading çifti
            timeframe: Zaman dilimi
            start_date: Başlangıç tarihi (opsiyonel)
            end_date: Bitiş tarihi (opsiyonel)

        Returns:
            pd.DataFrame: OHLCV verisi
        """
        conn = sqlite3.connect(self.db_path)

        # SQL sorgusu
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ?
        '''
        params = [symbol, timeframe]

        # Tarih filtreleri
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(int(start_date.timestamp() * 1000))
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(int(end_date.timestamp() * 1000))

        query += ' ORDER BY timestamp ASC'

        # Veriyi çek
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df.empty:
            return pd.DataFrame()

        # Timestamp'i datetime'a çevir
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        return df

    def fetch_and_save(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Tuple[pd.DataFrame, int]:
        """
        Veriyi çek ve veritabanına kaydet (helper method).

        Args:
            symbol: Trading çifti
            timeframe: Zaman dilimi
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi

        Returns:
            Tuple[pd.DataFrame, int]: (Veri DataFrame, Kaydedilen satır sayısı)
        """
        # Veriyi çek
        data = self.fetch_historical_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date
        )

        # Veritabanına kaydet
        inserted = self.save_to_db(data, symbol, timeframe)

        return data, inserted

    def stream_realtime_data(
        self,
        symbol: str,
        timeframe: str = '1m',
        callback: Optional[callable] = None
    ) -> None:
        """
        Canlı veri akışı (WebSocket - İleri seviye).

        Not: Bu metod WebSocket desteği olan exchange'ler için çalışır.
        Şu an placeholder olarak bırakılmıştır.

        Args:
            symbol: Trading çifti
            timeframe: Zaman dilimi
            callback: Her yeni mum geldiğinde çağrılacak fonksiyon
        """
        # TODO: WebSocket implementasyonu
        # Bu, exchange'e göre özelleştirilmeli
        # Örnek: ws = exchange.watch_ohlcv(symbol, timeframe)
        raise NotImplementedError(
            "WebSocket streaming henüz implemente edilmedi. "
            "Polling kullanarak gerçek zamanlı veri alabilirsiniz."
        )

    def get_available_symbols(self) -> List[str]:
        """
        Borsada mevcut olan trading çiftlerini listele.

        Returns:
            List[str]: Trading çiftleri listesi
        """
        try:
            markets = self.exchange.load_markets()
            return list(markets.keys())
        except Exception as e:
            print(f"Symbol listesi alınamadı: {e}")
            return []

    def get_latest_price(self, symbol: str) -> float:
        """
        Anlık fiyat bilgisi al.

        Args:
            symbol: Trading çifti

        Returns:
            float: Güncel fiyat
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            print(f"Fiyat alınamadı: {e}")
            return 0.0

    def __repr__(self) -> str:
        return (
            f"DataHandler(exchange={self.exchange_name}, "
            f"db={self.db_path}, testnet={self.testnet})"
        )
