"""
STEP 30: Mirror your real portfolio in the Alpaca PAPER account.

Reads my_portfolio.csv (your real holdings) and works out the paper orders that make
the paper account hold the SAME mix:
  - holdings in the paper account that aren't in your real portfolio -> sold
  - holdings that are too big or too small                           -> resized
  - real holdings the paper account doesn't have yet                  -> bought
Amounts use €1 = $1 of paper money, so the proportions match exactly.

PAPER MONEY ONLY. Dry run by default; you send the orders with --trade.
Your real portfolio and broker are never touched.

IMPORTANT: pause the Lesson 27 paper bot while mirroring, or it will buy and sell by its
own rule and undo the mirror. To remove just the bot's cron line:
    crontab -l | grep -v step27_paper_bot | crontab -

Run it with:   python step30_mirror.py            (dry run)
               python step30_mirror.py --trade    (send the paper orders)

New coding ideas in this lesson:
  - REBALANCING: target minus current = the trades you need
  - NOTIONAL orders: buy "$593 of NVDA" instead of a whole number of shares (fractional shares)
  - handling each order's errors separately, so one failure doesn't stop the rest
"""

import os
import sys

import pandas as pd
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from helpers import trading_client
from portfolio import rebalance_orders

# ================================ SETTINGS ================================
PORTFOLIO_FILE = "my_portfolio.csv"
TARGET_TOTAL = None  # None = use your real total (€1 = $1); or e.g. 3000 to scale everything
# ==========================================================================

really_trade = "--trade" in sys.argv
if not os.path.exists(PORTFOLIO_FILE):
    raise SystemExit(f"{PORTFOLIO_FILE} not found - see my_portfolio.example.csv")

real = pd.read_csv(PORTFOLIO_FILE).set_index("symbol")["value_eur"]
target = real * (TARGET_TOTAL / real.sum()) if TARGET_TOTAL else real

client = trading_client()  # paper account, always
clock = client.get_clock()
positions = {p.symbol: p for p in client.get_all_positions() if p.asset_class.value == "us_equity"}
current = pd.Series({s: float(p.market_value) for s, p in positions.items()}, dtype=float)
# Orders sent earlier that haven't filled yet (e.g. sent at the weekend). The positions
# above don't include them yet, so planning on top of them would DOUBLE every trade.
waiting = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500))

# Which target holdings can't be traded automatically?
problems = {}
for s in target.index:
    try:
        asset = client.get_asset(s)
        if not asset.tradable:
            problems[s] = "not tradable on Alpaca"
        elif not asset.fractionable:
            problems[s] = "whole shares only and no price data - can't size it in dollars"
    except APIError:
        problems[s] = "not found on Alpaca"
target_ok = target.drop(list(problems))

orders = rebalance_orders(current, target_ok)

mode = "TRADE (paper)" if really_trade else "DRY RUN (nothing sent)"
print(f"Mirror | {mode} | market {'OPEN' if clock.is_open else 'CLOSED'}")
print(f"Target: ${target.sum():,.2f} across {len(target)} holdings (your real total €{real.sum():,.2f}, €1 = $1)")
print(f"Paper account now: ${current.sum():,.2f} in {len(current)} positions\n")
if problems:
    for s, why in problems.items():
        print(f"  SKIP  {s:<6} ${target[s]:>8.2f}  ({why})")
    print()

if orders.empty:
    print("Nothing to do - the paper account already matches.")
for s, dollars in orders.items():
    if s not in target_ok:
        what = f"SELL ALL ({float(positions[s].qty):g} sh, ~${-dollars:,.2f}) - not in your real portfolio"
    elif dollars < 0:
        what = f"SELL ${-dollars:,.2f}  (now ${current.get(s, 0):,.2f} -> target ${target_ok[s]:,.2f})"
    else:
        what = f"BUY  ${dollars:,.2f}  (now ${current.get(s, 0):,.2f} -> target ${target_ok[s]:,.2f})"
    print(f"  {s:<6} {what}")

print(f"\nAfter mirroring: ~${target_ok.sum():,.2f} invested; the rest of the paper money stays as cash.")

if waiting:
    print(f"\n⚠ {len(waiting)} earlier order(s) are still waiting to fill:")
    for o in waiting:
        amount = f"${float(o.notional):,.2f}" if o.notional else f"{o.qty} sh"
        print(f"    {o.side.value:<4} {o.symbol:<6} {amount}")
    print("  The plan above doesn't include them yet. Wait until they fill (or cancel them with\n"
          "  'python step7_paper_order.py cancel'), then run this again. Nothing will be sent now.")
    sys.exit()

if not really_trade:
    print("\nDry run only. Pause the paper bot first (see the top of this file), then add --trade.")
    sys.exit()

# --- Send: sells first (they free up cash), then buys. Each order is tried on its own. ---------
print("\nSending paper orders...")
for s, dollars in orders.items():
    try:
        if s not in target_ok:
            client.close_position(s)  # sells the whole position, including any fraction of a share
            print(f"  {s:<6} sell-all sent")
        else:
            order = client.submit_order(MarketOrderRequest(
                symbol=s,
                notional=round(abs(dollars), 2),  # NOTIONAL = a dollar amount, not a share count
                side=OrderSide.SELL if dollars < 0 else OrderSide.BUY,
                time_in_force=TimeInForce.DAY,    # dollar-amount orders must be DAY orders
            ))
            print(f"  {s:<6} {'sell' if dollars < 0 else 'buy'} ${abs(dollars):,.2f} -> {order.status.value}")
    except APIError as error:
        print(f"  {s:<6} FAILED: {error}")  # carry on with the other orders

if not clock.is_open:
    print("\nThe market is closed: accepted orders fill at the next open. Run the dry run again "
          "after that to check the paper account matches.")
