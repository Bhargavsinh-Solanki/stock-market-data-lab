"""
STEP 27: A paper-trading bot that emails you its decisions.

PAPER MONEY ONLY - everything happens in Alpaca's practice account. The bot's choices
come from one simple rule (Lesson 5: own a stock while it's above its 50-day average).
That rule did WORSE than buy-and-hold in Lessons 5-6, so treat this as an experiment
to watch, not as recommendations for real money.

Each run, for every stock on the WATCHLIST:
  BUY       rule says own, we don't have it   -> buy ~BUDGET_PER_STOCK dollars (whole shares)
  HOLD      rule says own, we have it         -> keep it
  SELL      rule says cash, we have it        -> sell all of it
  STAY OUT  rule says cash, we don't have it  -> do nothing
  WAIT      an order is already pending       -> do nothing (never double up)
Stocks NOT on the watchlist are never touched.

SAFE BY DEFAULT:
  python lessons/step27_paper_bot.py                  dry run: shows decisions, sends nothing
  python lessons/step27_paper_bot.py --trade          sends the PAPER orders
  python lessons/step27_paper_bot.py --trade --email  ...and emails you the summary

New coding ideas in this lesson:
  - combining modules: data (helpers), decisions (paper_bot), orders (Alpaca), email (emailer)
  - a CASH CHECK: never plan to spend more paper money than the account has
  - "PURE" functions (paper_bot.decide) that are easy to test, kept apart from the
    parts that talk to the outside world (orders, email)
"""

import csv
import html
import os
import sys
from datetime import datetime

from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from lab.helpers import daily_closes, trading_client
from lab.paper_bot import BUY, HOLD, SELL, STAY_OUT, WAIT, decide, shares_for, trend_rule

# ============================== SETTINGS - change these freely ==============================
WATCHLIST = ["ZS", "NVDA", "CEG", "URTH", "SPY", "MRVL", "ORCL", "SPCX",
             "AAPL", "AVGO", "JNJ", "AMD", "QBTS"]   # Bayer (BAYRY) left out: no price data
BUDGET_PER_STOCK = 5_000   # paper dollars to spend when the bot buys a stock
MA_DAYS = 50               # the rule's moving-average length
EMAIL_WHEN = "trades"      # "trades" = only email when something is bought/sold; "always" = every run
LOG_FILE = "data/paper_bot_log.csv"
# ==============================================================================================

really_trade = "--trade" in sys.argv
send_mail = "--email" in sys.argv

trading = trading_client()  # paper account, always (see helpers.py)
clock = trading.get_clock()
account = trading.get_account()
cash = float(account.cash)
owned = {p.symbol: int(float(p.qty)) for p in trading.get_all_positions()}
pending = {o.symbol for o in trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))}

closes = daily_closes(WATCHLIST, days=MA_DAYS * 2 + 40, keep_gaps=True)
closes.index = closes.index.tz_convert("America/New_York").normalize()
if clock.is_open and closes.index[-1].date() == clock.timestamp.date():
    closes = closes.iloc[:-1]  # today's bar isn't finished yet - decide on finished days only

run_time = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
mode = "TRADE (paper)" if really_trade else "DRY RUN (nothing sent)"
print(f"Paper bot {run_time} | {mode} | market {'OPEN' if clock.is_open else 'CLOSED'} | "
      f"paper cash ${cash:,.0f}\n")

decisions = []
for symbol in WATCHLIST:
    close = closes[symbol].dropna() if symbol in closes else []
    if len(close) < MA_DAYS:
        decisions.append({"symbol": symbol, "action": "SKIPPED", "shares": 0, "price": 0, "average": 0,
                          "note": "not enough price history"})
        continue

    own, price, average = trend_rule(close, MA_DAYS)
    held = owned.get(symbol, 0)
    action = decide(own, held, symbol in pending)
    shares, note = 0, ""
    if action == BUY:
        shares = shares_for(BUDGET_PER_STOCK, price)
        cost = shares * price
        if shares == 0:
            action, note = "SKIPPED", "one share costs more than the budget"
        elif cost > cash:  # CASH CHECK: don't plan to spend money we don't have
            action, note = "SKIPPED", f"not enough paper cash (${cash:,.0f} left)"
        else:
            cash -= cost
    elif action in (SELL, HOLD):
        shares = held
    decisions.append({"symbol": symbol, "action": action, "shares": shares, "price": price,
                      "average": average, "note": note})

# --- Send the paper orders -------------------------------------------------------------------
for d in decisions:
    d["sent"] = False
    if really_trade and d["action"] in (BUY, SELL):
        order = trading.submit_order(MarketOrderRequest(
            symbol=d["symbol"], qty=d["shares"],
            side=OrderSide.BUY if d["action"] == BUY else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,  # if the market is closed, it waits for the next open
        ))
        d["sent"] = True
        d["note"] = f"order {order.status.value}"

# --- Show and log --------------------------------------------------------------------------------
for d in decisions:
    detail = (f"close ${d['price']:,.2f} vs {MA_DAYS}-day avg ${d['average']:,.2f}"
              if d["price"] else "")
    shares = f"{d['shares']} sh" if d["shares"] else ""
    print(f"  {d['symbol']:<5} {d['action']:<9} {shares:>7}  {detail}  {d['note']}")

os.makedirs("data", exist_ok=True)
is_new = not os.path.exists(LOG_FILE)
with open(LOG_FILE, "a", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["time", "symbol", "action", "shares", "price",
                                           "average", "note", "sent"])
    if is_new:
        writer.writeheader()
    for d in decisions:
        writer.writerow({"time": run_time, **{k: (round(v, 2) if isinstance(v, float) else v)
                                               for k, v in d.items()}})
print(f"\nLogged to {LOG_FILE}")

# --- Email ------------------------------------------------------------------------------------------
trades = [d for d in decisions if d["action"] in (BUY, SELL)]


def section(title, action):
    rows = [d for d in decisions if d["action"] == action]
    if not rows:
        return ""
    items = "".join(
        f"<li><b>{d['symbol']}</b>: {d['shares']} share{'' if d['shares'] == 1 else 's'} "
        f"at about ${d['price']:,.2f} "
        f"({MA_DAYS}-day average ${d['average']:,.2f}) {html.escape(d['note'])}</li>" for d in rows)
    return f"<h3>{title}</h3><ul>{items}</ul>"

when = ("Orders were sent to your PAPER account" if really_trade
        else "DRY RUN - nothing was sent")
if really_trade and not clock.is_open:
    when += " and will fill when the market next opens"
body = f"""<html><body style="font-family:Arial,sans-serif;color:#24292f;max-width:640px">
<h2>Paper bot - {datetime.now():%A %d %B %Y}</h2>
<p>{when}. Paper account value: <b>${float(account.portfolio_value):,.0f}</b>.</p>
{section("Bought" if really_trade else "Would buy", BUY)}{section("Sold" if really_trade else "Would sell", SELL)}{section("Holding", HOLD)}
{section("Waiting (order already pending)", WAIT)}
<p><b>Staying out:</b> {", ".join(d["symbol"] for d in decisions if d["action"] == STAY_OUT) or "none"}</p>
<p style="color:#57606a;font-size:12px">PAPER MONEY ONLY. Decisions come from one simple rule
(own while above the {MA_DAYS}-day average), which did worse than buy-and-hold in this project's
own tests. An experiment to follow - not investment advice or a recommendation for real money.</p>
</body></html>"""
with open("data/paper_bot_email.html", "w") as f:  # always save a preview of the email
    f.write(body)
print("Saved email preview: data/paper_bot_email.html")

if send_mail and (trades or EMAIL_WHEN == "always"):
    from lab.emailer import EmailError, send_email

    buys, sells = sum(d["action"] == BUY for d in decisions), sum(d["action"] == SELL for d in decisions)
    tag = "" if really_trade else "[DRY RUN] "
    try:
        send_email(f"{tag}Paper bot: {buys} buy, {sells} sell, "
                   f"{sum(d['action'] == HOLD for d in decisions)} holding", body)
        print("Email sent.")
    except EmailError as error:
        # The orders above already went through - don't crash, explain how to get the email later
        print(f"EMAIL NOT SENT: {error}")
        print("Fix .env, then send this run's summary with:  "
              "python -m lab.emailer --resend data/paper_bot_email.html")
elif send_mail:
    print("No buys or sells this run - no email (set EMAIL_WHEN = \"always\" to get one every run).")
