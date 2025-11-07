"""
Binance'den BTC-USDT verilerini indir ve Jesse veritabanına kaydet
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import ccxt
from datetime import datetime, timedelta
import time
import jesse.helpers as jh
from jesse.models import Candle
import arrow


def fetch_candles_from_binance(symbol='BTC/USDT', timeframe='1h', since_date='2023-01-01'):
    """
    Binance'den mum verilerini çek
    """
    print(f"\n{'='*70}")
    print(f"BINANCE VERİ İNDİRME")
    print(f"{'='*70}")
    print(f"Sembol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Başlangıç Tarihi: {since_date}")
    print(f"{'='*70}\n")

    # Binance exchange oluştur
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })

    # Başlangıç tarihini timestamp'e çevir
    since_timestamp = int(arrow.get(since_date, 'YYYY-MM-DD').timestamp() * 1000)

    all_candles = []
    current_timestamp = since_timestamp

    # Şimdiki zaman
    now = int(time.time() * 1000)

    batch_count = 0

    print("Veri indiriliyor... (Bu işlem uzun sürebilir)")
    print("Lütfen bekleyin...\n")

    while current_timestamp < now:
        try:
            # OHLCV verilerini çek (max 1000 mum)
            candles = exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since=current_timestamp,
                limit=1000
            )

            if not candles:
                break

            all_candles.extend(candles)
            batch_count += 1

            # İlerleme göster
            last_timestamp = candles[-1][0]
            last_date = datetime.fromtimestamp(last_timestamp / 1000)
            print(f"📊 Batch {batch_count}: {len(candles)} mum indirildi | Son tarih: {last_date.strftime('%Y-%m-%d %H:%M')}")

            # Bir sonraki batch için timestamp'i güncelle
            current_timestamp = last_timestamp + 1

            # Rate limiting
            time.sleep(exchange.rateLimit / 1000)

        except Exception as e:
            print(f"❌ Hata: {e}")
            time.sleep(5)
            continue

    print(f"\n✅ Toplam {len(all_candles)} mum indirildi!")
    return all_candles


def save_candles_to_jesse_db(candles, exchange_name='Binance Futures', symbol='BTC-USDT'):
    """
    İndirilen mumları Jesse veritabanına kaydet
    """
    print(f"\n{'='*70}")
    print(f"JESSE VERİTABANINA KAYIT")
    print(f"{'='*70}\n")

    # Jesse formatına çevir
    jesse_candles = []
    for candle in candles:
        # ccxt formatı: [timestamp, open, high, low, close, volume]
        jesse_candles.append({
            'id': jh.generate_unique_id(),
            'symbol': symbol,
            'exchange': exchange_name,
            'timestamp': candle[0],
            'open': candle[1],
            'high': candle[2],
            'low': candle[3],
            'close': candle[4],
            'volume': candle[5]
        })

    print(f"💾 {len(jesse_candles)} mum veritabanına kaydediliyor...")

    try:
        # Psycopg2 ile direkt bağlan
        import psycopg2

        conn = psycopg2.connect(
            host='127.0.0.1',
            database='jesse_db',
            user='voidstring',
            password=''
        )
        conn.autocommit = True  # Auto-commit her sorgudan sonra
        cursor = conn.cursor()

        # Candle tablosunu oluştur (Jesse formatında)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candle (
                id VARCHAR(30) PRIMARY KEY,
                timestamp BIGINT NOT NULL,
                open DOUBLE PRECISION NOT NULL,
                close DOUBLE PRECISION NOT NULL,
                high DOUBLE PRECISION NOT NULL,
                low DOUBLE PRECISION NOT NULL,
                volume DOUBLE PRECISION NOT NULL,
                exchange VARCHAR(30) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10) DEFAULT '1h'
            );
        ''')

        # Unique constraint ekle
        try:
            cursor.execute('''
                ALTER TABLE candle ADD CONSTRAINT candle_unique
                UNIQUE (exchange, symbol, timeframe, timestamp);
            ''')
        except:
            pass  # Zaten varsa geç

        print("✅ Candle tablosu hazır!")

        # Verileri kaydet
        print(f"\n💾 Veriler kaydediliyor...")
        successful = 0
        duplicates = 0

        for i, candle_data in enumerate(jesse_candles):
            if (i + 1) % 1000 == 0:
                print(f"  → {i+1}/{len(jesse_candles)} kayıt işleniyor...")

            try:
                cursor.execute('''
                    INSERT INTO candle (id, timestamp, open, close, high, low, volume, exchange, symbol, timeframe)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (exchange, symbol, timeframe, timestamp) DO NOTHING;
                ''', (
                    candle_data['id'],
                    candle_data['timestamp'],
                    candle_data['open'],
                    candle_data['close'],
                    candle_data['high'],
                    candle_data['low'],
                    candle_data['volume'],
                    candle_data['exchange'],
                    candle_data['symbol'],
                    '1h'  # timeframe
                ))
                if cursor.rowcount > 0:
                    successful += 1
                else:
                    duplicates += 1
            except Exception as e:
                if i < 5:  # İlk birkaç hatayı göster
                    print(f"⚠️  Kayıt {i} hatası: {e}")
                    print(f"   Veri: {candle_data}")
                pass
        cursor.close()
        conn.close()

        print(f"\n✅ Tüm veriler başarıyla kaydedildi!")
        print(f"   📊 Yeni kayıt: {successful}")
        print(f"   ⚠️  Duplicate (atlandı): {duplicates}")
        print(f"{'='*70}\n")

    except Exception as e:
        print(f"\n❌ Veritabanı hatası: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Ana fonksiyon"""
    try:
        # 1. Binance'den veri indir
        candles = fetch_candles_from_binance(
            symbol='BTC/USDT',
            timeframe='1h',
            since_date='2023-01-01'
        )

        # 2. Jesse veritabanına kaydet
        save_candles_to_jesse_db(candles)

        print("🎉 İşlem başarıyla tamamlandı!")
        print("Artık 'python run_backtest.py' komutuyla backtest yapabilirsin.\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  İşlem kullanıcı tarafından iptal edildi.")
    except Exception as e:
        print(f"\n❌ Beklenmeyen hata: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
