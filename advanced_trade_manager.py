"""
Gelişmiş İşlem Yönetimi Motoru
Trailing stop, partial exit, momentum-based exit gibi kurallar
"""
from typing import Dict, Optional, List
import numpy as np


class TradeManager:
    """
    Gelişmiş işlem yönetim kuralları:
    1. Trailing Stop Loss (Dinamik stop)
    2. Partial Exit (Kademeli çıkış)
    3. Momentum-Based Exit (Momentum kaybında çık)
    4. Time-Based Exit (Süre bazlı çıkış)
    5. Volatility-Based Stops (Volatilite bazlı stop)
    6. Breakeven Stop (Başabaş noktasına getir)
    """

    def __init__(self, config: Dict):
        """
        Args:
            config: {
                'use_trailing_stop': bool,
                'trailing_stop_activation': float,  # Trailing başlama (%)
                'trailing_stop_distance': float,     # Trailing mesafesi (%)

                'use_partial_exit': bool,
                'partial_exit_levels': List[Dict],  # [{'price_pct': 0.10, 'qty_pct': 0.5}]

                'use_momentum_exit': bool,
                'momentum_threshold': float,        # Momentum eşiği

                'use_time_exit': bool,
                'max_hold_bars': int,              # Max tutma süresi (mum sayısı)

                'use_breakeven': bool,
                'breakeven_activation': float,      # Breakeven başlama (%)
                'breakeven_offset': float          # Breakeven offset (%)
            }
        """
        self.config = config

    def update_position(self, position: Dict, current_price: float,
                       current_index: int, fractal_score: float = 0) -> Dict:
        """
        Pozisyonu güncelle ve çıkış kararı ver

        Args:
            position: Mevcut pozisyon bilgisi
            current_price: Güncel fiyat
            current_index: Güncel mum indexi
            fractal_score: Güncel fraktal skoru

        Returns:
            {
                'action': 'hold' | 'exit_partial' | 'exit_full',
                'exit_qty': float,
                'exit_reason': str,
                'updated_position': Dict
            }
        """
        if position is None:
            return {'action': 'hold', 'exit_qty': 0, 'exit_reason': None}

        entry_price = position['entry_price']
        current_qty = position.get('remaining_qty', position['qty'])
        bars_held = current_index - position.get('entry_index', 0)

        # Kar/Zarar hesapla
        pnl_pct = (current_price - entry_price) / entry_price * 100

        updated_position = position.copy()
        action = 'hold'
        exit_qty = 0
        exit_reason = None

        # 1. TRAILING STOP KONTROLÜ
        if self.config.get('use_trailing_stop', False):
            result = self._check_trailing_stop(
                position, current_price, pnl_pct
            )
            if result['triggered']:
                action = 'exit_full'
                exit_qty = current_qty
                exit_reason = 'Trailing Stop'
                return {
                    'action': action,
                    'exit_qty': exit_qty,
                    'exit_reason': exit_reason,
                    'updated_position': updated_position
                }

            updated_position['trailing_stop'] = result['new_stop']

        # 2. BREAKEVEN STOP KONTROLÜ
        if self.config.get('use_breakeven', False):
            result = self._check_breakeven(position, current_price, pnl_pct)
            updated_position['stop_loss'] = result['new_stop']

        # 3. PARTIAL EXIT KONTROLÜ
        if self.config.get('use_partial_exit', False):
            result = self._check_partial_exit(position, current_price, pnl_pct)
            if result['triggered']:
                action = 'exit_partial'
                exit_qty = result['exit_qty']
                exit_reason = f"Partial Exit {result['level']}"
                updated_position['remaining_qty'] = current_qty - exit_qty
                updated_position['partial_exits'] = position.get('partial_exits', []) + [
                    {'price': current_price, 'qty': exit_qty, 'reason': exit_reason}
                ]

        # 4. MOMENTUM EXIT KONTROLÜ
        if self.config.get('use_momentum_exit', False):
            if self._check_momentum_exit(fractal_score, position):
                action = 'exit_full'
                exit_qty = current_qty
                exit_reason = 'Momentum Loss'

        # 5. TIME-BASED EXIT KONTROLÜ
        if self.config.get('use_time_exit', False):
            max_bars = self.config.get('max_hold_bars', 50)
            if bars_held >= max_bars:
                action = 'exit_full'
                exit_qty = current_qty
                exit_reason = f'Time Exit ({bars_held} bars)'

        # 6. STANDART TP/SL KONTROLÜ
        if action == 'hold':
            tp = position.get('tp', float('inf'))
            sl = updated_position.get('stop_loss', position.get('sl', 0))

            if current_price >= tp:
                action = 'exit_full'
                exit_qty = current_qty
                exit_reason = 'Take Profit'
            elif current_price <= sl:
                action = 'exit_full'
                exit_qty = current_qty
                exit_reason = 'Stop Loss'

        return {
            'action': action,
            'exit_qty': exit_qty,
            'exit_reason': exit_reason,
            'updated_position': updated_position
        }

    def _check_trailing_stop(self, position: Dict, current_price: float,
                            pnl_pct: float) -> Dict:
        """Trailing stop kontrolü"""
        activation_pct = self.config.get('trailing_stop_activation', 5.0)
        distance_pct = self.config.get('trailing_stop_distance', 3.0)

        entry_price = position['entry_price']
        current_trailing = position.get('trailing_stop', 0)

        # Trailing henüz aktif değilse
        if pnl_pct < activation_pct:
            return {'triggered': False, 'new_stop': current_trailing}

        # Yeni trailing stop seviyesi
        new_stop = current_price * (1 - distance_pct / 100)

        # Trailing stop yukarı taşı (sadece yukarı hareket eder, aşağı inmez)
        if new_stop > current_trailing:
            current_trailing = new_stop

        # Trailing stop tetiklendi mi?
        triggered = current_price <= current_trailing

        return {'triggered': triggered, 'new_stop': current_trailing}

    def _check_breakeven(self, position: Dict, current_price: float,
                        pnl_pct: float) -> Dict:
        """Breakeven stop kontrolü"""
        activation_pct = self.config.get('breakeven_activation', 3.0)
        offset_pct = self.config.get('breakeven_offset', 0.5)

        entry_price = position['entry_price']
        current_sl = position.get('stop_loss', position.get('sl', 0))

        # Breakeven aktif mi?
        if pnl_pct >= activation_pct:
            # Stop'u breakeven + offset'e taşı
            breakeven_stop = entry_price * (1 + offset_pct / 100)

            # Sadece mevcut stop'tan yukarıysa güncelle
            if breakeven_stop > current_sl:
                return {'new_stop': breakeven_stop}

        return {'new_stop': current_sl}

    def _check_partial_exit(self, position: Dict, current_price: float,
                           pnl_pct: float) -> Dict:
        """Partial exit kontrolü"""
        levels = self.config.get('partial_exit_levels', [])
        completed_levels = position.get('completed_partial_levels', set())

        for i, level in enumerate(levels):
            target_pct = level['price_pct']
            qty_pct = level['qty_pct']

            # Bu seviye zaten tamamlandı mı?
            if i in completed_levels:
                continue

            # Hedefe ulaşıldı mı?
            if pnl_pct >= target_pct:
                exit_qty = position['qty'] * qty_pct
                return {
                    'triggered': True,
                    'exit_qty': exit_qty,
                    'level': f"{target_pct}%"
                }

        return {'triggered': False}

    def _check_momentum_exit(self, current_fractal_score: float,
                            position: Dict) -> bool:
        """Momentum kaybı kontrolü"""
        threshold = self.config.get('momentum_threshold', 20)
        entry_score = position.get('entry_fractal_score', 50)

        # Momentum %X kaybettiyse çık
        if current_fractal_score < entry_score * (threshold / 100):
            return True

        return False
