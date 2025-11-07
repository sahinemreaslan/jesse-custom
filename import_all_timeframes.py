"""
MULTI-TIMEFRAME VERİ İMPORT
═══════════════════════════════════════════════════════════
Tüm önemli timeframe'lerde veri import eder
30m, 2h, 4h, 8h, 12h, 1d
═══════════════════════════════════════════════════════════
"""
import ccxt
import psycopg2
from datetime import datetime, timedelta
import time


# İmport edilecek timeframe'ler
TIMEFRAMES = {
    '1m': '1 Dakika',
    '3m': '3 Dakika',
    '5m': '5 Dakika',
    '30m': '30 Dakika',
    '2h': '2 Saat',
    '4h': '4 Saat',
    '6h': '6 Saat',
    '8h': '8 Saat',
    '12h': '12 Saat',
    '1d': '1 Gün',
    '3d': '3 Gün',
    '1w': '1 Hafta',
}


def import_timeframe(timeframe, description, days=730):
    """Tek bir timeframe için veri import et"""

    # Çok kısa timeframe'ler için veri miktarını sınırla
    if timeframe in ['1m', '3m', '5m']:
        # 1m, 3m, 5m için sadece son 90 gün (veri çok büyük)
        days = min(days, 90)
        print(f"   ⚠️  {timeframe} için veri miktarı sınırlandırıldı: Son {days} gün")

    print("\n" + "="*80)
    print(f"📊 {description} ({timeframe}) VERİ İMPORT")
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

    # Tarih aralığı
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"\n📅 Tarih Aralığı:")
    print(f"   Başlangıç: {start_date.strftime('%Y-%m-%d')}")
    print(f"   Bitiş: {end_date.strftime('%Y-%m-%d')}")

    # Timestamp
    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    all_candles = []

    print(f"\n⏳ {timeframe} BTC-USDT verileri çekiliyor...")

    retry_count = 0
    max_retries = 3

    while since < end_ts:
        try:
            # Veriyi çek
            candles = exchange.fetch_ohlcv(
                'BTC/USDT',
                timeframe=timeframe,
                since=since,
                limit=1000
            )

            if not candles:
                break

            all_candles.extend(candles)

            # İlerleme
            current_date = datetime.fromtimestamp(candles[-1][0] / 1000)
            print(f"   📊 {len(all_candles)} mum çekildi... (Son: {current_date.strftime('%Y-%m-%d %H:%M')})", end='\r')

            # Bir sonraki batch
            since = candles[-1][0] + 1

            # Rate limit
            time.sleep(exchange.rateLimit / 1000)

            # Reset retry counter
            retry_count = 0

            # Bitiş kontrolü
            if since >= end_ts:
                break

        except Exception as e:
            retry_count += 1
            print(f"\n⚠️  Hata ({retry_count}/{max_retries}): {e}")

            if retry_count >= max_retries:
                print(f"\n❌ Maksimum deneme sayısına ulaşıldı. Devam ediliyor...")
                break

            time.sleep(5)
            continue

    print(f"\n\n✅ Toplam {len(all_candles)} mum çekildi")

    if len(all_candles) == 0:
        print("⚠️  Veri bulunamadı!")
        cursor.close()
        conn.close()
        return 0

    # Veritabanına kaydet
    print(f"\n⏳ Veritabanına kaydediliyor...")

    saved_count = 0
    updated_count = 0
    error_count = 0

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
                  'Binance Futures', 'BTC-USDT', timeframe))

            saved_count += 1

            if saved_count % 1000 == 0:
                conn.commit()
                print(f"   💾 {saved_count} mum kaydedildi...", end='\r')

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"   ⚠️  Kayıt hatası: {e}")
            continue

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n\n✅ {saved_count} mum veritabanına kaydedildi!")

    if error_count > 0:
        print(f"⚠️  {error_count} kayıt hatası oluştu")

    return saved_count


def check_existing_data():
    """Mevcut verileri kontrol et"""
    print("\n" + "="*80)
    print("MEVCUT VERİ KONTROLÜ")
    print("="*80 + "\n")

    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )
    cursor = conn.cursor()

    cursor.execute('''
        SELECT timeframe, COUNT(*) as count,
               MIN(timestamp) as first_ts,
               MAX(timestamp) as last_ts
        FROM candle
        WHERE symbol = 'BTC-USDT'
        GROUP BY timeframe
        ORDER BY timeframe
    ''')

    results = cursor.fetchall()

    print(f"{'Timeframe':<15} {'Mum Sayısı':<15} {'İlk Tarih':<20} {'Son Tarih':<20}")
    print("-" * 80)

    for row in results:
        timeframe = row[0]
        count = row[1]
        first_date = datetime.fromtimestamp(row[2] / 1000).strftime('%Y-%m-%d %H:%M')
        last_date = datetime.fromtimestamp(row[3] / 1000).strftime('%Y-%m-%d %H:%M')

        print(f"{timeframe:<15} {count:<15} {first_date:<20} {last_date:<20}")

    cursor.close()
    conn.close()

    print("\n" + "="*80)


def main():
    """Ana import fonksiyonu"""
    print("\n" + "="*80)
    print("MULTI-TIMEFRAME VERİ İMPORT")
    print("="*80)
    print("""
Bu script aşağıdaki timeframe'lerde veri import eder:

SCALPING (Çok Kısa Vadeli):
  - 1m (1 Dakika) - Son 90 gün
  - 3m (3 Dakika) - Son 90 gün
  - 5m (5 Dakika) - Son 90 gün

INTRADAY (Gün İçi):
  - 30m (30 Dakika) - Son 2 yıl

SWING TRADING (Orta/Uzun Vadeli):
  - 2h (2 Saat) - Son 2 yıl
  - 4h (4 Saat) - Son 2 yıl
  - 6h (6 Saat) - Son 2 yıl
  - 8h (8 Saat) - Son 2 yıl
  - 12h (12 Saat) - Son 2 yıl
  - 1d (1 Gün) - Son 2 yıl
  - 3d (3 Gün) - Son 2 yıl
  - 1w (1 Hafta) - Son 2 yıl

Zaten mevcut olan veriler:
  - 15m (15 Dakika)
  - 1h (1 Saat)

⚠️  DİKKAT:
  - 1m, 3m, 5m çok fazla veri (90 gün bile ~130k mum)
  - Toplam süre: ~45-60 dakika
  - Gerekli alan: ~2-3 GB
    """)

    # Mevcut verileri göster
    try:
        check_existing_data()
    except Exception as e:
        print(f"⚠️  Veri kontrolü başarısız: {e}")

    # Onay
    confirm = input("\nDevam etmek istiyor musunuz? (y/n): ").lower()

    if confirm != 'y':
        print("İptal edildi.")
        return

    # Her timeframe için import
    total_saved = 0
    results = {}

    for timeframe, description in TIMEFRAMES.items():
        try:
            saved = import_timeframe(timeframe, description)
            total_saved += saved
            results[timeframe] = saved
        except Exception as e:
            print(f"\n❌ {timeframe} import hatası: {e}")
            results[timeframe] = 0
            continue

    # Özet
    print("\n" + "="*80)
    print("İMPORT ÖZETİ")
    print("="*80 + "\n")

    print(f"{'Timeframe':<15} {'İmport Edilen':<20} {'Durum':<20}")
    print("-" * 80)

    for timeframe, count in results.items():
        status = "✅ Başarılı" if count > 0 else "❌ Başarısız"
        print(f"{timeframe:<15} {count:<20} {status:<20}")

    print(f"\nToplam: {total_saved} mum import edildi")

    # Güncel durum
    print("\n")
    check_existing_data()

    print("\n" + "="*80)
    print("✅ TAMAMLANDI!")
    print("="*80)

    print("\nŞimdi ne yapabilirsiniz:")
    print("  1. robustness_tester.py ile tüm timeframe'leri test edin")
    print("  2. 30m timeframe'i deneyin (15m ile 1h arası)")
    print("  3. 4h veya 1d gibi daha uzun timeframe'leri test edin")


if __name__ == '__main__':
    main()
