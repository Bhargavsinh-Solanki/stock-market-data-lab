"""
STEP 10: Organise your code - your own module + automated tests.

Compare this file with step4 and step5: same kind of work, a fraction of the code,
because the repeated parts now live in helpers.py.

For several stocks, it prints buy & hold vs the moving-average rule (after costs).

Run it with:   python step10_using_helpers.py
Run the tests: pytest
"""

import sys

from helpers import backtest, biggest_drop, daily_closes, grow_100

symbols = [s.upper() for s in sys.argv[1:]] or ["SPY", "QQQ", "AAPL", "MSFT", "TSLA"]
MA_DAYS = 50

closes = daily_closes(symbols, days=365 * 3)

print(f"{closes.index[0]:%Y-%m-%d} -> {closes.index[-1]:%Y-%m-%d}, rule: {MA_DAYS}-day average, 0.1% per switch\n")
print(f"{'Stock':<6}{'Buy & hold':>12}{'MA rule':>10}{'B&H drop':>10}{'Rule drop':>11}  Winner")
print("-" * 60)

for symbol in symbols:
    close = closes[symbol]
    hold_returns = close.pct_change().fillna(0)
    rule_returns = backtest(close, MA_DAYS)

    hold, rule = grow_100(hold_returns), grow_100(rule_returns)
    hold_drop = biggest_drop(100 * (1 + hold_returns).cumprod())
    rule_drop = biggest_drop(100 * (1 + rule_returns).cumprod())

    print(f"{symbol:<6}{hold:>12.2f}{rule:>10.2f}{hold_drop:>9.1f}%{rule_drop:>10.1f}%  "
          f"{'rule' if rule > hold else 'buy & hold'}")
