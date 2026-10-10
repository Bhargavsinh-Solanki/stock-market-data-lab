"""
STEP 16: Is it real, or just luck? (the shuffle test)

In Lessons 12 and 15 we found two patterns:
  A) "Busy news days have BIGGER price moves"          (Lesson 12)
  B) "After good-news days, the price tends to RISE"   (Lesson 15, AAPL: +0.64%)

Any pattern can appear by pure chance, especially with few days of data.
The SHUFFLE TEST asks: if I picked the same number of days AT RANDOM,
how often would they look at least this good?

  - Do that 10,000 times -> 10,000 "luck-only" results
  - If our real result beats almost all of them -> probably a REAL effect
  - If lots of random picks do just as well     -> could easily be LUCK

The fraction of random picks that did as well as ours is called the P-VALUE.
A common rule of thumb: p below 0.05 (5%) = "unlikely to be luck".

Part C then repeats both tests on 12 stocks. This guards against the
MULTIPLE TESTING trap: test 20 ideas and about 1 will pass "p < 0.05" by pure luck.
A real effect should show up again and again, not just once.

Run it with:   python lessons/step16_luck_test.py         (takes 1-2 minutes)
Other stocks:  python lessons/step16_luck_test.py NVDA MSFT

New coding ideas in this lesson:
  - NUMPY: fast maths on whole lists of numbers at once
  - RANDOM numbers with a SEED (so you get the same "random" result every run)
  - SIMULATION: answering a question by trying it thousands of times
  - HISTOGRAMS: a chart showing how often each value came up
"""

import os
import sys

import matplotlib.pyplot as plt

from lab.helpers import news_by_day, shuffle_test

symbols = [s.upper() for s in sys.argv[1:]] or ["AAPL", "TSLA"]
SCOREBOARD = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL",
              "META", "AMD", "NFLX", "JPM", "XOM", "INTC"]


def verdict(p):
    if p < 0.01:
        return "very unlikely to be luck"
    if p < 0.05:
        return "unlikely to be luck"
    if p < 0.20:
        return "weak - could be luck"
    return "looks like luck"


fig, axes = plt.subplots(len(symbols), 2, figsize=(12, 3.6 * len(symbols)), squeeze=False)

for row, symbol in enumerate(symbols):
    print(f"\n========== {symbol} ==========")
    _, table = news_by_day(symbol)

    # --- Test A: busy news days -> bigger moves? -------------------------------------
    size = table["move_%"].abs()
    busy = table["stories"] > table["stories"].quantile(0.8)
    ours, shuffled, p = shuffle_test(size, busy)
    print(f"A) Busy news days ({busy.sum()} of {len(table)}): avg size of move {ours:.2f}% "
          f"vs {size.mean():.2f}% on a typical day")
    print(f"   Random picks that did as well: {p:.1%}  ->  {verdict(p)}")

    ax = axes[row][0]
    ax.hist(shuffled, bins=50, color="lightgray")
    ax.axvline(ours, color="red", linewidth=2, label=f"Busy news days ({ours:.2f}%)")
    ax.set_title(f"{symbol} A) size of move on {busy.sum()} random days vs busy news days\n"
                 f"p = {p:.3f}: {verdict(p)}", fontsize=10)
    ax.set_xlabel("Average size of move (%)")
    ax.legend(fontsize=8)

    # --- Test B: good-news days -> next day goes up? ----------------------------------
    nxt = table.dropna(subset=["next_day_move_%"])  # the last day has no "tomorrow" yet
    good = nxt["mood"] > 0
    ours, shuffled, p = shuffle_test(nxt["next_day_move_%"], good)
    print(f"B) Good-news days ({good.sum()} of {len(nxt)}): avg NEXT-day move {ours:+.2f}% "
          f"vs {nxt['next_day_move_%'].mean():+.2f}% on a typical day")
    print(f"   Random picks that did as well: {p:.1%}  ->  {verdict(p)}")

    ax = axes[row][1]
    ax.hist(shuffled, bins=50, color="lightgray")
    ax.axvline(ours, color="red", linewidth=2, label=f"Good-news days ({ours:+.2f}%)")
    ax.set_title(f"{symbol} B) next-day move on {good.sum()} random days vs good-news days\n"
                 f"p = {p:.3f}: {verdict(p)}", fontsize=10)
    ax.set_xlabel("Average next-day move (%)")
    ax.legend(fontsize=8)

print("\nGray bars = 10,000 random picks of days (what luck alone produces).")
print("Red line  = our real result. Far to the right of the gray = hard to explain by luck.")

plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig("data/luck_test.png")
print("Saved chart to data/luck_test.png")

# --- Part C: the scoreboard - does each effect show up AGAIN on other stocks? --------
print(f"\n========== Scoreboard: both tests on {len(SCOREBOARD)} stocks ==========")
print(f"{'Stock':<7}{'A) busy -> bigger move':>24}{'B) good news -> up tomorrow':>30}")
passed_a = passed_b = 0
for symbol in SCOREBOARD:
    try:
        _, table = news_by_day(symbol)
        busy = table["stories"] > table["stories"].quantile(0.8)
        _, _, p_a = shuffle_test(table["move_%"].abs(), busy)

        nxt = table.dropna(subset=["next_day_move_%"])
        _, _, p_b = shuffle_test(nxt["next_day_move_%"], nxt["mood"] > 0)
    except Exception as error:
        print(f"{symbol:<7} skipped ({error})")
        continue

    passed_a += p_a < 0.05
    passed_b += p_b < 0.05
    mark = lambda p: f"p={p:.3f} {'PASS' if p < 0.05 else '    '}"
    print(f"{symbol:<7}{mark(p_a):>24}{mark(p_b):>30}")

expected = len(SCOREBOARD) * 0.05
print(f"\nPassed (p < 0.05):   A = {passed_a} of {len(SCOREBOARD)}    B = {passed_b} of {len(SCOREBOARD)}")
print(f"Expected by pure luck: about {expected:.1f} of {len(SCOREBOARD)} for an idea that does NOTHING.")
