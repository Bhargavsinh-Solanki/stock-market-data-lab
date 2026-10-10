"""
STEP 33: Your portfolio through euro eyes.

You invest in euros, but your holdings are priced in US dollars. This lesson splits
your results into "what the companies did" and "what the exchange rate did":

  1. How the euro moved against the dollar (1 week to 1 year)
  2. Your holdings' returns in $ and in €, and the currency's part
  3. Your whole mix over the past year, in $ and in €
  4. Does the currency make your ride bumpier or calmer?

Facts and risk ranges only - not financial advice.

Run it with:   python step33_euro_view.py

New coding ideas in this lesson:
  - converting between currencies: (1 + return in $) / (1 + euro's change) - 1
  - DECOMPOSING a result into parts (company vs currency)
  - aligning two data sources on the same dates (reindex + forward-fill)
"""

import os

import matplotlib.pyplot as plt
import pandas as pd

from currency import euro_strength, split_return, to_euro_prices
from helpers import daily_closes
from performers import PERIODS, top_performers
from risk_forecast import forecast_holdings

holdings = pd.read_csv("my_portfolio.csv").set_index("symbol")
euro = euro_strength()

# --- 1. The euro vs the dollar --------------------------------------------------------------------
print("1. The euro against the dollar (up = euro stronger = your US holdings worth LESS in €)")
for name, days in PERIODS.items():
    change = (euro.iloc[-1] / euro.iloc[-1 - days] - 1) * 100
    print(f"   last {name:<9} {change:+6.2f}%")

# --- 2. Each holding in $ and in € -----------------------------------------------------------------
usd_closes = daily_closes(list(holdings.index), days=400, keep_gaps=True)
eur_closes = to_euro_prices(usd_closes, euro)
period = "1 year"
usd = top_performers(usd_closes, PERIODS[period])["return_%"]
eur = top_performers(eur_closes, PERIODS[period])["return_%"]
table = pd.DataFrame({"in $": usd, "in €": eur}).dropna()
table["currency part"] = table["in €"] - table["in $"]
print(f"\n2. Your holdings over the last {period} (holdings listed for less than a year are left out):")
print(f"   {'':<6}{'in $':>9}{'in €':>9}{'from the currency':>20}")
for s, r in table.sort_values("in €", ascending=False).iterrows():
    print(f"   {s:<6}{r['in $']:>+8.1f}%{r['in €']:>+8.1f}%{r['currency part']:>+19.1f} pts")

# --- 3. The whole mix ------------------------------------------------------------------------------
covered = table.index
weights = holdings.loc[covered, "value_eur"] / holdings.loc[covered, "value_eur"].sum()
mix_usd = (table["in $"] * weights).sum()
euro_change = (euro.iloc[-1] / euro.iloc[-1 - PERIODS[period]] - 1) * 100
in_eur, currency_part = split_return(mix_usd, euro_change)
print(f"\n3. Your mix over the last {period} ({len(covered)} holdings, today's weights):")
print(f"   in dollars {mix_usd:+.1f}%  ->  in euros {in_eur:+.1f}%  "
      f"(the exchange rate added {currency_part:+.1f} points)")

# --- 4. Risk in $ vs in € ----------------------------------------------------------------------------
values = holdings["value_eur"]
_, mix_usd_risk, _ = forecast_holdings(values)
_, mix_eur_risk, _ = forecast_holdings(values, in_euros=True)
u, e = mix_usd_risk.iloc[0]["typical_%"], mix_eur_risk.iloc[0]["typical_%"]
print(f"\n4. Next month's typical swing for your mix:  in $ ±{u:.1f}%   in € ±{e:.1f}%")
if abs(e - u) < 0.5:
    print("   The currency makes almost no difference to how bumpy your ride is right now.")
elif e < u:
    print(f"   The currency makes your ride calmer by {u - e:.1f} points "
          "(the dollar often rises when stocks fall, softening drops for euro investors).")
else:
    print(f"   The currency makes your ride bumpier by {e - u:.1f} points.")
print("\nFacts and risk ranges only - not financial advice.")

# --- Chart: the mix in $ and in € over the year ------------------------------------------------------
daily_usd = usd_closes[covered].pct_change()
daily_eur = eur_closes[covered].pct_change()
start = usd_closes.index[-1 - PERIODS[period]]
growth = pd.DataFrame({
    "Your mix in $": 100 * (1 + (daily_usd.loc[start:].iloc[1:] * weights).sum(axis=1)).cumprod(),
    "Your mix in €": 100 * (1 + (daily_eur.loc[start:].iloc[1:] * weights).sum(axis=1)).cumprod(),
})
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(growth.index, growth["Your mix in $"], label="Your mix in $")
ax.plot(growth.index, growth["Your mix in €"], label="Your mix in €")
ax.set_ylabel("Start = 100")
ax.grid(alpha=0.3)
fx_ax = ax.twinx()  # second axis: the euro's strength (Lesson 25's twin axis)
fx_ax.plot(euro.loc[start:].index, euro.loc[start:] / euro.loc[start] * 100, color="gray",
           linestyle=":", label="Euro vs dollar (start = 100)")
fx_ax.set_ylabel("Euro vs dollar")
lines = ax.get_legend_handles_labels(), fx_ax.get_legend_handles_labels()
ax.legend(lines[0][0] + lines[1][0], lines[0][1] + lines[1][1], loc="upper left")
ax.set_title(f"Your mix over the last {period}: in dollars vs in euros")
plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig("data/euro_view.png")
print("Saved chart to data/euro_view.png")
