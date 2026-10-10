"""
STEP 36: Dividends - the cash your holdings pay out.

For each holding in my_portfolio.csv:
  - how often it paid a dividend in the last 12 months, and how much per share
  - its DIVIDEND YIELD (a year of dividends / today's price)
  - a rough yearly income on YOUR amount, before tax
  - the next ex-date: "announced" (already published) or an "estimate" from its usual rhythm

Facts only - not financial advice.

Run it with:   python lessons/step36_dividends.py

New coding ideas in this lesson:
  - working with DATES: date arithmetic, "the last 12 months", estimating the next date
  - "announced" vs "estimated" data, and labelling which is which
  - a second Alpaca data source: corporate actions
"""

import os
from datetime import date, timedelta

import matplotlib.pyplot as plt
import pandas as pd

from lab.dividends import fetch_cash_dividends, summarise
from lab.helpers import daily_closes

holdings = pd.read_csv("my_portfolio.csv").set_index("symbol")
symbols = list(holdings.index)

closes = daily_closes(symbols, days=10, keep_gaps=True)
prices = {s: closes[s].dropna().iloc[-1] for s in closes.columns if closes[s].notna().any()}
dividends = fetch_cash_dividends(symbols)
table = summarise(dividends, prices, holdings["value_eur"])

payers = table[table["payments_12m"] > 0]
quiet = [s for s in table.index if table.loc[s, "payments_12m"] == 0]
print(f"Dividends over the last 12 months - {len(payers)} of your {len(table)} holdings paid one\n")
print(f"  {'':<6}{'name':<22}{'paid':>6}{'per share':>11}{'yield':>8}{'≈ € a year':>12}   next ex-date")
for s, r in payers.iterrows():
    when = f"{r['next_date']:%d %b %Y} ({r['next_is']})" if r["next_date"] else "-"
    if pd.isna(r["yield_%"]):  # paid, but no price data to work out the yield
        yld, income = "n/a", "n/a"
    else:
        yld, income = f"{r['yield_%']:.2f}%", f"€{r['income_year']:.2f}"
    print(f"  {s:<6}{holdings.loc[s, 'name']:<22}{r['payments_12m']:>5}x{'$' + format(r['per_share_12m'], '.2f'):>11}"
          f"{yld:>8}{income:>12}   {when}")

total = table["income_year"].sum()  # sum() skips the "n/a" (NaN) holdings
portfolio = holdings["value_eur"].sum()
print(f"\n  Rough total: about €{total:.2f} a year on €{portfolio:,.0f} "
      f"(a yield of {total / portfolio:.2%} for the whole portfolio), before tax.")
print(f"  No dividends in the last 12 months: {', '.join(quiet)}")
print("""
Good to know (check your own situation):
  - TAX: dividends are taxed. US companies usually withhold 15% for EU residents, and your
    country may tax them again (Germany counts them toward the yearly tax-free allowance).
  - YOUR ETFs: many EU (UCITS) ETFs are "ACCUMULATING" - they reinvest dividends inside the
    fund instead of paying cash. If yours is "Acc", you won't see these payments - they're
    already in the price. "Dist" (distributing) ETFs pay cash.
  - Fast-growing companies often pay nothing and reinvest instead (here: Zscaler, AMD, D-Wave).
  - Since Lesson 19, the price data includes dividends ("Adjustment.ALL"), so earlier returns
    already counted them.
Facts only - not financial advice.""")

# --- Chart: the next 6 months as a calendar -------------------------------------------------------
soon = table[(table["next_is"] != "-")].copy()
soon = soon[soon["next_date"] <= date.today() + timedelta(days=183)]
if len(soon):
    fig, ax = plt.subplots(figsize=(10, 3 + 0.3 * len(soon)))
    for i, (s, r) in enumerate(soon.sort_values("next_date").iterrows()):
        colour = "C2" if r["next_is"] == "announced" else "C0"
        ax.scatter(pd.Timestamp(r["next_date"]), i, s=80 + 10 * r["income_year"], color=colour)
        ax.annotate(f"{s}  ~€{r['income_year'] / max(r['payments_12m'], 1):.2f}",
                    (pd.Timestamp(r["next_date"]), i), xytext=(8, -4), textcoords="offset points")
    ax.set_yticks([])
    ax.set_title("Next ex-dates (green = announced, blue = estimate; size = yearly income)")
    ax.grid(alpha=0.3, axis="x")
    plt.tight_layout()
    os.makedirs("data", exist_ok=True)
    plt.savefig("data/dividend_calendar.png")
    print("\nSaved chart to data/dividend_calendar.png")
