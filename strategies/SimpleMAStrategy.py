"""
Simple Moving Average Crossover Strategy
EMA(8) ve EMA(21) çapraz geçiş stratejisi
"""
from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils


class SimpleMAStrategy(Strategy):
    """
    Basit EMA Crossover Stratejisi

    Giriş: EMA(8) > EMA(21)
    Çıkış: Take Profit veya Stop Loss
    """

    @property
    def ema_short(self):
        """Kısa EMA (8 period)"""
        return ta.ema(self.candles, period=8)

    @property
    def ema_long(self):
        """Uzun EMA (21 period)"""
        return ta.ema(self.candles, period=21)

    def should_long(self) -> bool:
        """
        Long pozisyon açma koşulu
        EMA(8) > EMA(21) olduğunda true döner
        """
        return self.ema_short > self.ema_long

    def should_short(self) -> bool:
        """Short pozisyon açmıyoruz"""
        return False

    def go_long(self):
        """
        Long pozisyon aç
        - Bakiyenin %5'i ile gir
        - %10 take profit
        - %5 stop loss
        """
        # Pozisyon büyüklüğünü hesapla (bakiyenin %5'i)
        qty = utils.size_to_qty(
            self.available_margin * 0.05,
            self.price,
            fee_rate=self.fee_rate
        )

        # Market order ile giriş
        self.buy = qty, self.price

        # Take profit: %10 kar hedefi
        self.take_profit = qty, self.price * 1.10

        # Stop loss: %5 zarar durdur
        self.stop_loss = qty, self.price * 0.95

    def go_short(self):
        """Short pozisyon açmıyoruz"""
        pass

    def should_cancel_entry(self) -> bool:
        """Entry order'ları iptal et"""
        return True

    def filters(self) -> list:
        """
        Filtreler - opsiyonel
        Pozisyon açmadan önce ek kontroller
        """
        return []
