"""
RSI Mean Reversion Strategy
RSI aşırı satım bölgesindeyken alım yapar
"""
from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils


class RSIMeanReversion(Strategy):
    """
    RSI Mean Reversion Stratejisi

    Giriş: RSI < 30 (Oversold - aşırı satım)
    Çıkış: RSI > 70 (Overbought - aşırı alım) veya TP/SL

    Mantık: Fiyat çok düştüğünde (RSI 30 altı) al,
            çok yükseldiğinde (RSI 70 üstü) sat
    """

    @property
    def rsi(self):
        """RSI(14) hesapla"""
        return ta.rsi(self.candles, period=14)

    def should_long(self) -> bool:
        """
        Long pozisyon açma koşulu
        RSI 30'un altındaysa (oversold)
        """
        return self.rsi < 30

    def should_short(self) -> bool:
        """Short pozisyon açmıyoruz"""
        return False

    def should_cancel_entry(self) -> bool:
        """Entry iptal koşulu"""
        return True

    def go_long(self):
        """
        Long pozisyon aç
        - Bakiyenin %10'u ile gir (daha agresif)
        - %15 take profit
        - %7 stop loss
        """
        # Pozisyon büyüklüğünü hesapla (bakiyenin %10'u)
        qty = utils.size_to_qty(
            self.available_margin * 0.10,
            self.price,
            fee_rate=self.fee_rate
        )

        # Market order ile giriş
        self.buy = qty, self.price

        # Take profit: %15 kar hedefi
        self.take_profit = qty, self.price * 1.15

        # Stop loss: %7 zarar durdur
        self.stop_loss = qty, self.price * 0.93

    def update_position(self):
        """
        Pozisyon güncellemesi
        RSI 70'i geçerse pozisyonu kapat (overbought)
        """
        if self.is_long and self.rsi > 70:
            self.liquidate()

    def go_short(self):
        """Short pozisyon açmıyoruz"""
        pass

    def filters(self) -> list:
        """Filtreler"""
        return []
