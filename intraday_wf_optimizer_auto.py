"""
INTRADAY WALK-FORWARD OPTIMIZER (AUTO)
═══════════════════════════════════════════════════════════
15 dakikalık timeframe için walk-forward optimizasyon
Otomatik çalışır (input gerektirmez)
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

from intraday_walk_forward_optimizer import IntradayWalkForwardOptimizer

if __name__ == '__main__':
    print("\n" + "="*80)
    print("INTRADAY WALK-FORWARD OPTIMIZER (AUTO)")
    print("="*80)
    print("\n🚀 Optimizasyon otomatik başlatılıyor...\n")

    optimizer = IntradayWalkForwardOptimizer(initial_capital=10000)
    optimizer.run()
