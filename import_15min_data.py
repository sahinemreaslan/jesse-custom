"""
15 DAKİKALIK VERİ İMPORT - İntraday Trading İçin
═══════════════════════════════════════════════════════════
Binance'den 15 dakikalık BTC-USDT verilerini çeker
═══════════════════════════════════════════════════════════
"""
import ccxt
import psycopg2
from datetime import datetime, timedelta
import time

def import_15min_data():
    """15 dakikalık verileri çek"""

    print("="*80)
    print("15 DAKİKALIK VERİ İMPORT - INTRADAY")
    print("="*80)

    # Binance bağlantısı
    print("\n⏳ Binance'e bağlanılıyor...")
    exchange = ccxt.binance({'enableRateLimit': True})

    # PostgreSQL bağlantısı
    print("⏳ Veritabanına bağlanılıyor...")
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )
    cursor = conn.cursor()

    # Son 2 yıl (2023-2025) - walk-forward optimizasyon için
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)  # 2 yıl

    print(f"\n📅 Tarih Aralığı:")
    print(f"   Başlangıç: {start_date.strftime('%Y-%m-%d')}")
    print(f"   Bitiş: {end_date.strftime('%Y-%m-%d')}")

    # Timestamp
    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    all_candles = []

    print(f"\n⏳ 15 dakikalık BTC-USDT verileri çekiliyor...")

    while since < end_ts:
        try:
            # 15 dakikalık mumlar
            candles = exchange.fetch_ohlcv(
                'BTC/USDT',
                timeframe='15m',
                since=since,
                limit=1000
            )

            if not candles:
                break

            all_candles.extend(candles)

            # İlerleme
            current_date = datetime.fromtimestamp(candles[-1][0] / 1000)
            print(f"   📊 {len(all_candles)} mum çekildi... (Son: {current_date.strftime('%Y-%m-%d %H:%M')})")

            # Bir sonraki batch
            since = candles[-1][0] + 1

            # Rate limit
            time.sleep(exchange.rateLimit / 1000)

            # Bitiş kontrolü
            if since >= end_ts:
                break

        except Exception as e:
            print(f"\n❌ Hata: {e}")
            time.sleep(5)
            continue

    print(f"\n✅ Toplam {len(all_candles)} mum çekildi")

    # Veritabanına kaydet
    print(f"\n⏳ Veritabanına kaydediliyor...")

    saved_count = 0
    for candle in all_candles:
        timestamp = candle[0]
        open_price = candle[1]
        high = candle[2]
        low = candle[3]
        close = candle[4]
        volume = candle[5]

        try:
            cursor.execute('''
                INSERT INTO candle (id, timestamp, open, close, high, low, volume, exchange, symbol, timeframe)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (exchange, symbol, timeframe, timestamp)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    close = EXCLUDED.close,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    volume = EXCLUDED.volume
            ''', (timestamp, open_price, close, high, low, volume,
                  'Binance Futures', 'BTC-USDT', '15m'))

            saved_count += 1

            if saved_count % 1000 == 0:
                conn.commit()
                print(f"   💾 {saved_count} mum kaydedildi...")

        except Exception as e:
            print(f"   ⚠️  Kayıt hatası: {e}")
            continue

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n✅ {saved_count} mum veritabanına kaydedildi!")
    print("\n" + "="*80)
    print("✅ 15 dakikalık veri import tamamlandı!")
    print("="*80)

if __name__ == '__main__':
    import_15min_data()
