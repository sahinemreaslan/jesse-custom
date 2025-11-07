"""
ADIM 3: RİSK/REWARD ANALİZİ
═══════════════════════════════════════════════════════════
Amaç: Stratejinin risk profilini detaylı analiz et
      - Sharpe Ratio (Risk-adjusted return)
      - Maximum Drawdown
      - Win/Loss Ratio ve Profit Factor
      - Risk of Ruin (Batma riski)
      - Expectancy (Beklenen değer)
      - Consecutive Loss analizi

Neden: Strateji karlı olabilir ama risk profili kabul edilemez olabilir.
       Gerçek trade yapmadan önce risk metriklerini anlamalıyız.
═══════════════════════════════════════════════════════════
"""
import sys
sys.path.insert(0, '/home/voidstring/Desktop/jesse_real')

import psycopg2
import pandas as pd
import numpy as np
from fractal_analyzer import FractalAnalyzer, MultiTimeframeFractalAnalyzer
from advanced_trade_manager import TradeManager


def load_data():
    """2023 yılı verilerini yükle (referans periyot)"""
    conn = psycopg2.connect(
        host='127.0.0.1',
        database='jesse_db',
        user='voidstring',
        password=''
    )

    query = '''
        SELECT timestamp, open, high, low, close, volume
        FROM candle
        WHERE exchange = 'Binance Futures'
          AND symbol = 'BTC-USDT'
          AND timeframe = '1h'
          AND timestamp >= 1672531200000
          AND timestamp <= 1704067199000
        ORDER BY timestamp ASC;
    '''

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def run_backtest_with_tracking(df):
    """Partial Exit Pro stratejisini detaylı takip ile çalıştır"""
    config = {
        'entry_patterns': ['Trending Up', 'Outside Bar'],
        'min_strength': 30,
        'position_size': 0.20,
        'tp_percent': 0.30,
        'sl_percent': 0.10,
        'weights': {
            'TRENDING_UP': 2.5,
            'OUTSIDE_BAR': 3.0,
            'TRENDING_DOWN': 2.0,
            'INSIDE_BAR': 0.5
        },
        'trade_management': {
            'use_partial_exit': True,
            'partial_exit_levels': [
                {'price_pct': 8.0, 'qty_pct': 0.33},
                {'price_pct': 15.0, 'qty_pct': 0.33},
            ],
            'use_trailing_stop': True,
            'trailing_stop_activation': 10.0,
            'trailing_stop_distance': 4.0,
            'use_breakeven': True,
            'breakeven_activation': 5.0,
            'breakeven_offset': 1.0,
            'use_momentum_exit': False,
            'use_time_exit': False
        }
    }

    # Fraktal analiz
    df = FractalAnalyzer.analyze_series(df)
    analyzer = MultiTimeframeFractalAnalyzer(weights=config['weights'])
    df = analyzer.calculate_fractal_score(df)

    # Trade manager
    trade_manager = TradeManager(config['trade_management'])

    # Backtest
    balance = 10000
    position = None
    trades = []
    balance_history = [10000]
    equity_curve = []

    for i in range(50, len(df)):
        row = df.iloc[i]
        price = row['close']
        pattern = row.get('fractal_pattern')
        strength = row.get('fractal_strength', 0)
        fractal_score = row.get('fractal_score', 0)

        # Pozisyon güncelleme
        if position is not None:
            update_result = trade_manager.update_position(
                position, price, i, fractal_score
            )

            if update_result['action'] in ['exit_full', 'exit_partial']:
                qty = update_result['exit_qty']
                profit = (price - position['entry_price']) * qty
                balance += profit

                if update_result['action'] == 'exit_full':
                    trades.append({
                        'entry_price': position['entry_price'],
                        'exit_price': price,
                        'profit': profit,
                        'profit_pct': ((price - position['entry_price']) / position['entry_price']) * 100,
                        'balance_after': balance,
                        'exit_reason': update_result['exit_reason'],
                        'bars_held': i - position['entry_index']
                    })
                    position = None
                else:
                    position = update_result['updated_position']
            else:
                position = update_result['updated_position']

        # Yeni giriş
        if position is None and pattern in config['entry_patterns'] and strength >= config['min_strength']:
            qty = (balance * config['position_size']) / price
            position = {
                'entry_price': price,
                'qty': qty,
                'remaining_qty': qty,
                'entry_index': i,
                'entry_fractal_score': fractal_score,
                'tp': price * (1 + config['tp_percent']),
                'sl': price * (1 - config['sl_percent']),
                'stop_loss': price * (1 - config['sl_percent']),
                'trailing_stop': 0,
                'partial_exits': []
            }

        balance_history.append(balance)

        # Equity curve (pozisyon varsa unrealized P/L dahil)
        if position:
            unrealized = (price - position['entry_price']) * position['remaining_qty']
            equity_curve.append(balance + unrealized)
        else:
            equity_curve.append(balance)

    return {
        'trades': trades,
        'balance_history': balance_history,
        'equity_curve': equity_curve,
        'final_balance': balance
    }


def calculate_risk_metrics(result):
    """Risk metriklerini hesapla"""
    trades = result['trades']
    equity_curve = np.array(result['equity_curve'])

    if len(trades) == 0:
        return None

    # Temel istatistikler
    profits = [t['profit'] for t in trades]
    winning_trades = [t for t in trades if t['profit'] > 0]
    losing_trades = [t for t in trades if t['profit'] < 0]

    num_wins = len(winning_trades)
    num_losses = len(losing_trades)

    # 1. Win Rate
    win_rate = (num_wins / len(trades)) * 100 if len(trades) > 0 else 0

    # 2. Average Win/Loss
    avg_win = np.mean([t['profit'] for t in winning_trades]) if winning_trades else 0
    avg_loss = np.mean([t['profit'] for t in losing_trades]) if losing_trades else 0

    # 3. Profit Factor (Total Win / Total Loss)
    total_win = sum([t['profit'] for t in winning_trades])
    total_loss = abs(sum([t['profit'] for t in losing_trades]))
    profit_factor = total_win / total_loss if total_loss > 0 else float('inf')

    # 4. Expectancy (Beklenen kazanç per trade)
    expectancy = np.mean(profits)

    # 5. Maximum Drawdown
    peak = np.maximum.accumulate(equity_curve)
    drawdown = ((equity_curve - peak) / peak) * 100
    max_drawdown = drawdown.min()

    # 6. Sharpe Ratio (Risk-adjusted return)
    returns = np.diff(equity_curve) / equity_curve[:-1]
    sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(8760) if np.std(returns) > 0 else 0  # Annualized

    # 7. Maximum Consecutive Losses
    consecutive_losses = 0
    max_consecutive_losses = 0
    for t in trades:
        if t['profit'] < 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0

    # 8. Risk of Ruin (simplified Kelly Criterion based)
    win_prob = win_rate / 100
    loss_prob = 1 - win_prob
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    # Kelly Criterion
    kelly_pct = (win_prob * win_loss_ratio - loss_prob) / win_loss_ratio if win_loss_ratio > 0 else 0

    # 9. Recovery Factor (Net Profit / Max Drawdown)
    net_profit = result['final_balance'] - 10000
    recovery_factor = net_profit / abs(max_drawdown * 10000 / 100) if max_drawdown != 0 else 0

    # 10. Largest Win/Loss
    largest_win = max([t['profit'] for t in winning_trades]) if winning_trades else 0
    largest_loss = min([t['profit'] for t in losing_trades]) if losing_trades else 0

    return {
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'win_loss_ratio': win_loss_ratio,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'max_consecutive_losses': max_consecutive_losses,
        'kelly_criterion': kelly_pct * 100,
        'recovery_factor': recovery_factor,
        'largest_win': largest_win,
        'largest_loss': largest_loss,
        'num_wins': num_wins,
        'num_losses': num_losses
    }


def main():
    """Ana analiz fonksiyonu"""
    print("="*80)
    print("ADIM 3: RİSK/REWARD ANALİZİ")
    print("="*80)
    print("\nStrateji: Partial Exit Pro (957% getiri)")
    print("Periyot: 2023 Yılı")
    print("\n" + "="*80)

    # Veri yükle
    print("\n📊 Veri yükleniyor...")
    df = load_data()
    print(f"✅ {len(df)} mum yüklendi (2023 yılı)")

    # Backtest çalıştır
    print("\n⏳ Backtest çalıştırılıyor...\n")
    result = run_backtest_with_tracking(df)

    # Risk metrikleri hesapla
    metrics = calculate_risk_metrics(result)

    if metrics is None:
        print("❌ Yeterli işlem bulunamadı!")
        return

    # SONUÇLAR
    print("="*80)
    print("📊 TEMEL İSTATİSTİKLER")
    print("="*80)

    net_profit = result['final_balance'] - 10000
    roi = (net_profit / 10000) * 100

    print(f"\n💰 FİNANSAL PERFORMANS:")
    print(f"   Başlangıç Sermaye: $10,000")
    print(f"   Final Sermaye: ${result['final_balance']:,.2f}")
    print(f"   Net Kar: ${net_profit:+,.2f}")
    print(f"   ROI: {roi:+.2f}%")

    print(f"\n📊 İŞLEM İSTATİSTİKLERİ:")
    print(f"   Toplam İşlem: {len(result['trades'])}")
    print(f"   Kazanan: {metrics['num_wins']} ({metrics['win_rate']:.1f}%)")
    print(f"   Kaybeden: {metrics['num_losses']} ({100-metrics['win_rate']:.1f}%)")

    # RİSK METRİKLERİ
    print("\n" + "="*80)
    print("⚖️  RİSK/REWARD METRİKLERİ")
    print("="*80)

    print(f"\n🎯 KAZANÇ/KAYIP ANALİZİ:")
    print(f"   Ortalama Kazanç: ${metrics['avg_win']:,.2f}")
    print(f"   Ortalama Kayıp: ${metrics['avg_loss']:,.2f}")
    print(f"   Win/Loss Oranı: {metrics['win_loss_ratio']:.2f}x")
    print(f"   En Büyük Kazanç: ${metrics['largest_win']:,.2f}")
    print(f"   En Büyük Kayıp: ${metrics['largest_loss']:,.2f}")

    print(f"\n💹 PERFORMANS METRİKLERİ:")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Expectancy (per trade): ${metrics['expectancy']:,.2f}")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")

    print(f"\n🛡️  RİSK METRİKLERİ:")
    print(f"   Maximum Drawdown: {metrics['max_drawdown']:.2f}%")
    print(f"   Recovery Factor: {metrics['recovery_factor']:.2f}")
    print(f"   Max Ardışık Kayıp: {metrics['max_consecutive_losses']} işlem")

    print(f"\n📐 POZİSYON BOYUTU ÖNERİSİ:")
    print(f"   Kelly Criterion: %{metrics['kelly_criterion']:.2f}")
    print(f"   Mevcut Kullanım: %20.00")

    if metrics['kelly_criterion'] < 20:
        print(f"   ⚠️  Uyarı: Kelly kriterinin üstünde pozisyon kullanıyorsunuz!")
    else:
        print(f"   ✅ Pozisyon boyutu Kelly kriteri içinde")

    # DEĞERLENDİRME
    print("\n" + "="*80)
    print("📋 GENEL DEĞERLENDİRME")
    print("="*80)

    # Risk skorları
    risk_score = 0
    total_checks = 0

    print("\n✓ Kontrol Listesi:\n")

    # 1. Win Rate
    total_checks += 1
    if metrics['win_rate'] >= 50:
        print(f"   ✅ Win Rate: {metrics['win_rate']:.1f}% (>50% - İyi)")
        risk_score += 1
    else:
        print(f"   ⚠️  Win Rate: {metrics['win_rate']:.1f}% (<50% - Düşük)")

    # 2. Profit Factor
    total_checks += 1
    if metrics['profit_factor'] >= 1.5:
        print(f"   ✅ Profit Factor: {metrics['profit_factor']:.2f} (>1.5 - Mükemmel)")
        risk_score += 1
    elif metrics['profit_factor'] >= 1.2:
        print(f"   ⚠️  Profit Factor: {metrics['profit_factor']:.2f} (1.2-1.5 - Orta)")
    else:
        print(f"   ❌ Profit Factor: {metrics['profit_factor']:.2f} (<1.2 - Zayıf)")

    # 3. Sharpe Ratio
    total_checks += 1
    if metrics['sharpe_ratio'] >= 1.0:
        print(f"   ✅ Sharpe Ratio: {metrics['sharpe_ratio']:.2f} (>1.0 - İyi)")
        risk_score += 1
    else:
        print(f"   ⚠️  Sharpe Ratio: {metrics['sharpe_ratio']:.2f} (<1.0 - Düşük)")

    # 4. Max Drawdown
    total_checks += 1
    if abs(metrics['max_drawdown']) < 20:
        print(f"   ✅ Max Drawdown: {metrics['max_drawdown']:.2f}% (<20% - Kabul Edilebilir)")
        risk_score += 1
    elif abs(metrics['max_drawdown']) < 30:
        print(f"   ⚠️  Max Drawdown: {metrics['max_drawdown']:.2f}% (20-30% - Yüksek)")
    else:
        print(f"   ❌ Max Drawdown: {metrics['max_drawdown']:.2f}% (>30% - Çok Yüksek)")

    # 5. Win/Loss Ratio
    total_checks += 1
    if metrics['win_loss_ratio'] >= 2.0:
        print(f"   ✅ Win/Loss Ratio: {metrics['win_loss_ratio']:.2f}x (>2.0 - Mükemmel)")
        risk_score += 1
    elif metrics['win_loss_ratio'] >= 1.5:
        print(f"   ⚠️  Win/Loss Ratio: {metrics['win_loss_ratio']:.2f}x (1.5-2.0 - İyi)")
    else:
        print(f"   ❌ Win/Loss Ratio: {metrics['win_loss_ratio']:.2f}x (<1.5 - Zayıf)")

    # SKOR
    score_pct = (risk_score / total_checks) * 100

    print(f"\n{'='*80}")
    print(f"📊 RİSK SKORU: {risk_score}/{total_checks} ({score_pct:.0f}%)")
    print(f"{'='*80}")

    if score_pct >= 80:
        print("\n✅ SONUÇ: Strateji MÜKEMMEL risk/reward profiline sahip!")
        print("   → Gerçek trade için uygun")
    elif score_pct >= 60:
        print("\n⚠️  SONUÇ: Strateji İYİ ama bazı iyileştirmeler gerekli")
        print("   → Dikkatli kullanılabilir")
    else:
        print("\n❌ SONUÇ: Strateji risk profili ZAYIF!")
        print("   → Daha fazla optimizasyon gerekli")

    print("\n" + "="*80)
    print("✅ Adım 3 tamamlandı!")
    print("="*80)


if __name__ == '__main__':
    main()
