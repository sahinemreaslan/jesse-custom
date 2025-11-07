"""
PAPER TRADING LOG GÖRÜNTÜLEYICI
═══════════════════════════════════════════════════════════
paper_trading_log.json dosyasını okur ve detaylı rapor gösterir

Kullanım:
  python view_paper_trades.py
═══════════════════════════════════════════════════════════
"""
import json
import os
from datetime import datetime


def view_trades():
    """Trade log'unu görüntüle"""

    log_file = 'paper_trading_log.json'

    if not os.path.exists(log_file):
        print("="*80)
        print("⚠️  PAPER TRADING LOG BULUNAMADI")
        print("="*80)
        print(f"\nHenüz paper trading başlatılmamış.")
        print(f"Başlatmak için: python paper_trading_engine.py")
        return

    # Log'u oku
    with open(log_file, 'r') as f:
        data = json.load(f)

    # Rapor
    print("="*80)
    print("PAPER TRADING LOG - DETAYLI RAPOR")
    print("="*80)

    print(f"\n📊 GENEL BİLGİLER:")
    print(f"   Strateji: {data['strategy']}")
    print(f"   Symbol: {data['symbol']}")
    print(f"   Başlangıç Sermaye: ${data['initial_capital']:,.2f}")
    print(f"   Güncel Sermaye: ${data['current_capital']:,.2f}")

    profit = data['current_capital'] - data['initial_capital']
    roi = (profit / data['initial_capital']) * 100

    print(f"\n💰 PERFORMANS:")
    print(f"   Kar/Zarar: ${profit:+,.2f}")
    print(f"   ROI: {roi:+.2f}%")
    print(f"   Toplam Trade: {data['total_trades']}")

    if data['total_trades'] == 0:
        print("\n⚠️  Henüz trade yok!")
        return

    trades = data['trades']

    # İstatistikler
    winning = [t for t in trades if t['profit'] > 0]
    losing = [t for t in trades if t['profit'] < 0]

    print(f"\n📈 İŞLEM İSTATİSTİKLERİ:")
    print(f"   Kazanan: {len(winning)} ({len(winning)/len(trades)*100:.1f}%)")
    print(f"   Kaybeden: {len(losing)} ({len(losing)/len(trades)*100:.1f}%)")

    if winning:
        avg_win = sum([t['profit'] for t in winning]) / len(winning)
        max_win = max([t['profit'] for t in winning])
        print(f"   Ort. Kazanç: ${avg_win:+,.2f}")
        print(f"   En Büyük Kazanç: ${max_win:+,.2f}")

    if losing:
        avg_loss = sum([t['profit'] for t in losing]) / len(losing)
        max_loss = min([t['profit'] for t in losing])
        print(f"   Ort. Zarar: ${avg_loss:+,.2f}")
        print(f"   En Büyük Zarar: ${max_loss:+,.2f}")

    # Profit factor
    if losing:
        total_win = sum([t['profit'] for t in winning])
        total_loss = abs(sum([t['profit'] for t in losing]))
        pf = total_win / total_loss if total_loss > 0 else float('inf')
        print(f"   Profit Factor: {pf:.2f}")

    # Çıkış sebepleri
    exit_reasons = {}
    for t in trades:
        reason = t['exit_reason']
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    print(f"\n🎯 ÇIKIŞ SEBEPLERİ:")
    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(trades)) * 100
        print(f"   {reason:20} → {count:2} trade ({pct:.1f}%)")

    # Trade listesi
    print(f"\n{'='*80}")
    print(f"TRADE DETAYLARI")
    print(f"{'='*80}\n")

    print(f"{'#':<4} {'Giriş':<17} {'Çıkış':<17} {'Pattern':<15} {'P/L':<12} {'P/L %':<10} {'Sebep':<15}")
    print("─" * 100)

    for i, trade in enumerate(trades, 1):
        emoji = "✅" if trade['profit'] > 0 else "❌"

        print(f"{i:<4} {trade['entry_time']:<17} {trade['exit_time']:<17} "
              f"{trade['pattern']:<15} ${trade['profit']:>8,.2f} "
              f"{trade['profit_pct']:>6.2f}%   {trade['exit_reason']:<15} {emoji}")

    print(f"\n{'='*80}")
    print(f"✅ Toplam {len(trades)} trade gösteriliyor")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    view_trades()
