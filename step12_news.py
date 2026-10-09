"""
STEP 12: Does news move prices?

Goal:
  (a) download 6 months of news headlines for a stock from Alpaca
  (b) count how many stories came out for each trading day
  (c) JOIN that with the daily price moves (two tables matched up by date)
  (d) check: are busy news days also big price-move days?

Watch out for TIMING: a story published after the 16:00 New York close can
only affect the NEXT day's price. helpers.trading_day_for() handles this,
and tests/test_helpers.py checks it.

Run it with:   python step12_news.py
Other stock:   python step12_news.py TSLA

New coding ideas in this lesson:
  - JOINING two tables on a shared column (the date)
  - GROUPING rows and counting them (like a pivot table in Excel)
  - CORRELATION: one number saying how strongly two things move together
"""

import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
from alpaca.data.requests import NewsRequest

from helpers import daily_closes, news_client, trading_day_for

symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
DAYS = 180
MAX_TICKERS = 3  # ignore round-up articles that mention lots of companies at once

# --- (a) News ---------------------------------------------------------------------
print(f"Downloading {DAYS} days of {symbol} news...")
news = news_client().get_news(
    NewsRequest(symbols=symbol, start=datetime.now() - timedelta(days=DAYS))
).df

# Keep stories that are mainly ABOUT this company, not "50 stocks to watch" lists.
focused = news[news["symbols"].apply(len) <= MAX_TICKERS].copy()
print(f"  {len(news)} stories, {len(focused)} focused on {symbol} (≤{MAX_TICKERS} tickers)\n")

# --- Prices: the daily move, in % ---------------------------------------------------
close = daily_closes(symbol, days=DAYS + 10)
close.index = close.index.tz_localize(None).normalize()  # plain dates, no time zone
prices = pd.DataFrame({"close": close, "move_%": close.pct_change() * 100}).dropna()
prices["size_of_move_%"] = prices["move_%"].abs()  # up or down - we just want "how big"

# --- (b) Which trading day does each story belong to? ------------------------------
focused["trading_day"] = trading_day_for(focused["created_at"], prices.index)

# GROUP: one row per trading day, counting the stories
stories_per_day = focused.groupby("trading_day").size().rename("stories")

# --- (c) JOIN prices and news counts on the date -----------------------------------
# "left" join = keep every price day, even those with zero stories (fill with 0)
table = prices.join(stories_per_day, how="left").fillna({"stories": 0})
table["stories"] = table["stories"].astype(int)
# Prices were fetched a few extra days back (to compute the first move). Drop the days
# before the news window, or they'd wrongly look like "zero-story" days.
news_start = pd.Timestamp(datetime.now() - timedelta(days=DAYS)).normalize()
table = table[table.index > news_start]

# --- (d) Compare quiet vs busy days ------------------------------------------------
busy_cutoff = table["stories"].quantile(0.8)  # top 20% of days by number of stories
busy = table[table["stories"] > busy_cutoff]
quiet = table[table["stories"] <= busy_cutoff]

print(f"{len(table)} trading days, {table['stories'].sum()} stories matched")
print(f"Average stories per day: {table['stories'].mean():.1f}\n")
print(f"{'':<34}{'Days':>6}{'Avg size of move':>18}")
print(f"{'Quiet days (≤' + format(busy_cutoff, '.0f') + ' stories)':<34}{len(quiet):>6}"
      f"{quiet['size_of_move_%'].mean():>17.2f}%")
print(f"{'Busy days (>' + format(busy_cutoff, '.0f') + ' stories)':<34}{len(busy):>6}"
      f"{busy['size_of_move_%'].mean():>17.2f}%")

corr = table["stories"].corr(table["size_of_move_%"])
print(f"\nCorrelation between number of stories and size of move: {corr:+.2f}")
print("  (+1 = always move together, 0 = no link, -1 = opposite)")

# The 5 biggest moves, with that day's most recent focused headline
print(f"\nBiggest {symbol} moves and a headline from that day:")
top = table.sort_values("size_of_move_%", ascending=False).head(5)
for day, row in top.iterrows():
    stories = focused[focused["trading_day"] == day]
    headline = stories["headline"].iloc[0] if len(stories) else "(no focused stories)"
    print(f"  {day:%Y-%m-%d}  {row['move_%']:+6.2f}%  {int(row['stories']):>3} stories  "
          f"{headline[:70]}")

# --- Chart -------------------------------------------------------------------------
fig, (top_ax, mid_ax, scatter_ax) = plt.subplots(
    3, 1, figsize=(11, 10), gridspec_kw={"height_ratios": [1, 1, 1.3]}
)
top_ax.bar(table.index, table["stories"], color="gray")
top_ax.set_title(f"{symbol}: focused news stories per trading day")
top_ax.grid(alpha=0.3)

colors = ["green" if m > 0 else "red" for m in table["move_%"]]
mid_ax.bar(table.index, table["move_%"], color=colors)
mid_ax.set_title(f"{symbol}: daily price move (%)")
mid_ax.grid(alpha=0.3)

scatter_ax.scatter(table["stories"], table["size_of_move_%"], alpha=0.6)
scatter_ax.set_xlabel("Number of stories that day")
scatter_ax.set_ylabel("Size of move (%)")
scatter_ax.set_title(f"Each dot is one day - correlation {corr:+.2f}")
scatter_ax.grid(alpha=0.3)

plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig(f"data/{symbol}_news.png")
print(f"\nSaved chart to data/{symbol}_news.png")
