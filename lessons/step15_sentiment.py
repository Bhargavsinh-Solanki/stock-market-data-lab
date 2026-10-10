"""
STEP 15: Is the news good or bad? (sentiment analysis)

Lesson 12 counted HOW MANY stories came out. Now we ask WHAT KIND:
  1. Score every headline: +1 per good word ("beats", "soars"), -1 per bad word ("misses", "falls")
  2. Average the scores for each trading day -> a "mood" for that day
  3. Two questions:
       SAME DAY: on good-news days, did the price usually go UP?
       NEXT DAY: does today's mood PREDICT tomorrow's move?   <- the one a trader cares about

Run it with:   python lessons/step15_sentiment.py
Other stock:   python lessons/step15_sentiment.py TSLA

New coding ideas in this lesson:
  - SETS: {"beat", "soars"} - a bag of unique words with very fast "is it in here?" checks
  - REGULAR EXPRESSIONS (regex): patterns for finding text, e.g. r"[a-z]+" = "a run of letters"
  - .apply(): run a function on every row of a column
  - .shift(-1): look at the NEXT row (tomorrow) - fine here, because we're
    checking a prediction against what really happened, not trading on it
"""

import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
from alpaca.data.requests import NewsRequest

from lab.helpers import daily_closes, headline_sentiment, news_client, trading_day_for

symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
DAYS = 180
MAX_TICKERS = 3

# --- 1. Download and score the headlines ---------------------------------------------
print(f"Downloading {DAYS} days of {symbol} news...")
news = news_client().get_news(
    NewsRequest(symbols=symbol, start=datetime.now() - timedelta(days=DAYS))
).df
news = news[news["symbols"].apply(len) <= MAX_TICKERS].copy()

# .apply() runs headline_sentiment on every headline, one by one
news["score"] = news["headline"].apply(headline_sentiment)

counts = news["score"].apply(lambda s: "positive" if s > 0 else "negative" if s < 0 else "neutral")
print(f"  {len(news)} focused headlines: "
      + ", ".join(f"{n} {label}" for label, n in counts.value_counts().items()) + "\n")

# --- 2. One mood per trading day -----------------------------------------------------
close = daily_closes(symbol, days=DAYS + 10)
close.index = close.index.tz_localize(None).normalize()
prices = pd.DataFrame({"move_%": close.pct_change() * 100})
prices["next_day_move_%"] = prices["move_%"].shift(-1)  # tomorrow's move, on today's row

news["trading_day"] = trading_day_for(news["created_at"], prices.index)
mood = news.groupby("trading_day")["score"].mean().rename("mood")

# "inner" join = keep only days that HAVE news (a day with no stories has no mood)
table = prices.join(mood, how="inner").dropna(subset=["move_%"])
table["label"] = pd.cut(table["mood"], [-99, -0.001, 0.001, 99],
                        labels=["bad news", "neutral", "good news"])

# --- 3. The two questions ------------------------------------------------------------
summary = table.groupby("label", observed=True).agg(
    days=("mood", "size"),
    same_day_avg=("move_%", "mean"),
    same_day_up=("move_%", lambda m: (m > 0).mean() * 100),
    next_day_avg=("next_day_move_%", "mean"),
    next_day_up=("next_day_move_%", lambda m: (m > 0).mean() * 100),
)
print(f"{len(table)} trading days with news\n")
print(f"{'':<11}{'Days':>6}  {'SAME DAY':^22}  {'NEXT DAY':^22}")
print(f"{'':<11}{'':>6}  {'avg move':>10}{'% up':>10}    {'avg move':>10}{'% up':>10}")
for label, row in summary.iterrows():
    print(f"{label:<11}{int(row['days']):>6}  {row['same_day_avg']:>+9.2f}%{row['same_day_up']:>9.0f}%"
          f"    {row['next_day_avg']:>+9.2f}%{row['next_day_up']:>9.0f}%")

same = table["mood"].corr(table["move_%"])
nxt = table["mood"].corr(table["next_day_move_%"])
print(f"\nCorrelation of mood with SAME-day move: {same:+.2f}")
print(f"Correlation of mood with NEXT-day move: {nxt:+.2f}")

# --- Examples: where the word list works, and where it gets fooled -------------------
print("\nMost positive headlines:")
for _, r in news.nlargest(3, "score").iterrows():
    print(f"  {r['score']:+d}  {r['headline'][:90]}")
print("Most negative headlines:")
for _, r in news.nsmallest(3, "score").iterrows():
    print(f"  {r['score']:+d}  {r['headline'][:90]}")

# "Fooled": positive-scored headlines on the biggest DOWN days
worst_days = table.nsmallest(3, "move_%").index
fooled = news[news["trading_day"].isin(worst_days) & (news["score"] > 0)]
if len(fooled):
    print("Fooled? Positive-scored headlines on the biggest DOWN days:")
    for _, r in fooled.head(3).iterrows():
        move = table.loc[r["trading_day"], "move_%"]
        print(f"  {r['score']:+d}  ({move:+.1f}% that day)  {r['headline'][:80]}")

# --- Chart ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 4.5))
x = range(len(summary))
ax.bar([i - 0.2 for i in x], summary["same_day_avg"], width=0.4, label="Same day")
ax.bar([i + 0.2 for i in x], summary["next_day_avg"], width=0.4, label="Next day")
ax.set_xticks(list(x), [f"{lab}\n({d} days)" for lab, d in zip(summary.index, summary["days"])])
ax.axhline(0, color="gray", linewidth=1)
ax.set_ylabel("Average price move (%)")
ax.set_title(f"{symbol}: price moves after good vs bad news days")
ax.legend()
ax.grid(alpha=0.3, axis="y")
plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig(f"data/{symbol}_sentiment.png")
print(f"\nSaved chart to data/{symbol}_sentiment.png")
