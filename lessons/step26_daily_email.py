"""
STEP 26: A daily market report by email.

Every run builds a report with:
  - YOUR RULE ALERTS: e.g. "a single stock is above 20% of your portfolio"
  - YOUR HOLDINGS: how each moved, and your estimated portfolio move
  - MARKET OVERVIEW: S&P 500, MSCI World, Nasdaq and the main sectors
  - HEADLINES for your holdings from the last 24 hours
  - NEXT MONTH'S NORMAL RANGE: the Lesson 28 risk forecast (added in Lesson 29)

Facts and your own rules only - it never says what to buy, hold or sell.

PREVIEW by default: saves data/daily_report.html (open it in a browser).
Add --send to email it (needs the email settings in .env - see emailer.py).

Run it with:   python lessons/step26_daily_email.py          (preview)
               python lessons/step26_daily_email.py --send   (preview + send)

New coding ideas in this lesson:
  - HTML: the language of web pages, also used for good-looking emails
  - SMTP: the standard way programs send email; App Passwords
  - ESCAPING text (html.escape) so a headline can't break or hijack the page
  - SAFE BY DEFAULT: preview unless you explicitly ask to send
"""

import os
import sys
from datetime import datetime

import pandas as pd

from lab.report import build_html, check_rules, headlines, holdings_moves, market_overview
from lab.risk_forecast import forecast_holdings

# ======================= YOUR RULES - set these to YOUR own limits =======================
RULES = {
    "max_single_stock_%": 20,   # alert if one stock is more than this % of your portfolio
    "max_sector_%": 50,         # alert if stocks from one sector are more than this %
    "daily_move_alert_%": 5,    # alert if a holding moves more than ± this % in a day
}
PORTFOLIO_FILE = "my_portfolio.csv"
# ==========================================================================================

if not os.path.exists(PORTFOLIO_FILE):
    raise SystemExit(f"{PORTFOLIO_FILE} not found - see my_portfolio.example.csv")
holdings = pd.read_csv(PORTFOLIO_FILE).set_index("symbol")
today = datetime.now()

print("Building the report...")
market = market_overview()
mine, portfolio_day, missing = holdings_moves(holdings)
alerts = check_rules(holdings, mine, RULES)
news = headlines(list(holdings.index))
risk = forecast_holdings(holdings["value_eur"])  # Lesson 29: next month's normal range

report = build_html(market, mine, portfolio_day, missing, alerts, news, today, risk=risk)
os.makedirs("data", exist_ok=True)
with open("data/daily_report.html", "w") as f:
    f.write(report)

print(f"  Your holdings: about {portfolio_day:+.2f}% on the latest trading day (today so far if the market is open)")
print(f"  S&P 500: {market.loc['SPY', 'day_%']:+.2f}%   MSCI World: {market.loc['URTH', 'day_%']:+.2f}%")
print(f"  {len(alerts)} rule alert(s), {len(news)} headline(s)")
print(f"  Next month's normal range for your mix: ±{risk[1].iloc[0]['typical_%']:.1f}% (2 months in 3)")
for a in alerts:
    print(f"   - {a}")
print("Saved preview: data/daily_report.html")

if "--send" in sys.argv:
    from lab.emailer import EmailError, send_email  # only needed when sending

    subject = (f"Market report {today:%d %b}: your holdings {portfolio_day:+.1f}%"
               + (f" · {len(alerts)} alert(s)" if alerts else ""))
    try:
        send_email(subject, report)
        print("Email sent.")
    except EmailError as error:
        print(f"EMAIL NOT SENT: {error}")
else:
    print("Preview only. Add --send to email it.")
