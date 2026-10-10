"""
STEP 7: Your first paper order.

This lesson ALWAYS uses the paper (practice) account - fake money only.
It is hard-coded below and ignores the ALPACA_PAPER setting on purpose.

Two kinds of order:
  - MARKET order: "Buy it now at whatever the current price is."
                  Fills almost instantly, but you don't control the exact price.
  - LIMIT order:  "Buy it only if the price is $X or lower."
                  You control the price, but it might never fill.

Commands (type them after the file name):
  python lessons/step7_paper_order.py                     -> show account, positions, orders
  python lessons/step7_paper_order.py buy AAPL            -> market order: buy 1 share
  python lessons/step7_paper_order.py limit AAPL 300      -> limit order: buy 1 share at $300 or less
  python lessons/step7_paper_order.py sell AAPL           -> market order: sell 1 share
  python lessons/step7_paper_order.py cancel              -> cancel all orders that haven't filled yet

New coding ideas in this lesson:
  - reading COMMANDS from the terminal and choosing what to do with if / elif
  - asking the user to confirm with input()
"""

import os
import sys

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest

load_dotenv()

# paper=True is fixed here: this lesson can never touch real money.
client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True,
)


def show_status():
    """Print market hours, cash, what we own, and recent orders."""
    clock = client.get_clock()
    if clock.is_open:
        print(f"Market is OPEN (closes {clock.next_close:%Y-%m-%d %H:%M} ET)")
    else:
        print(f"Market is CLOSED (opens {clock.next_open:%Y-%m-%d %H:%M} ET)")

    account = client.get_account()
    print(f"Paper cash: ${float(account.cash):,.2f}   "
          f"Total value: ${float(account.portfolio_value):,.2f}\n")

    # Positions = stocks we currently own
    positions = client.get_all_positions()
    print("What you own:")
    if not positions:
        print("  (nothing yet)")
    for p in positions:
        print(f"  {p.symbol:<6} {p.qty:>4} shares  bought at ${float(p.avg_entry_price):.2f}  "
              f"now ${float(p.current_price):.2f}  profit/loss ${float(p.unrealized_pl):+.2f}")

    # Orders = instructions we've sent (filled, waiting, or cancelled)
    orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=5))
    print("\nLast 5 orders:")
    if not orders:
        print("  (none yet)")
    for o in orders:
        limit = f" @ ${o.limit_price}" if o.limit_price else ""
        filled = f" filled at ${float(o.filled_avg_price):.2f}" if o.filled_avg_price else ""
        print(f"  {o.submitted_at:%m-%d %H:%M}  {o.side.value:<4} {o.qty} {o.symbol:<6} "
              f"{o.type.value}{limit}  -> {o.status.value}{filled}")


def confirm(message):
    """Ask a yes/no question in the terminal. Only 'y' counts as yes."""
    return input(f"{message} [y/N] ").strip().lower() == "y"


def send(order_request, description):
    """Confirm, then send an order to Alpaca and report what happened."""
    if not confirm(f"PAPER account: {description}. Send it?"):
        print("Cancelled - nothing was sent.")
        return
    order = client.submit_order(order_request)
    print(f"Sent! Order id {order.id}, status: {order.status.value}")
    print("Run 'python lessons/step7_paper_order.py' in a few seconds to see if it filled.")


# --- Read the command typed in the terminal -----------------------------------
command = sys.argv[1].lower() if len(sys.argv) > 1 else "status"

if command == "status":
    show_status()

elif command in ("buy", "sell") and len(sys.argv) == 3:
    symbol = sys.argv[2].upper()
    send(
        MarketOrderRequest(
            symbol=symbol,
            qty=1,
            side=OrderSide.BUY if command == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,  # if unfilled, it expires at today's close
        ),
        f"MARKET {command.upper()} 1 share of {symbol}",
    )

elif command == "limit" and len(sys.argv) == 4:
    symbol, price = sys.argv[2].upper(), round(float(sys.argv[3]), 2)
    send(
        LimitOrderRequest(
            symbol=symbol,
            qty=1,
            side=OrderSide.BUY,
            limit_price=price,
            time_in_force=TimeInForce.DAY,
        ),
        f"LIMIT BUY 1 share of {symbol} at ${price} or lower",
    )

elif command == "cancel":
    if confirm("Cancel ALL open (unfilled) paper orders?"):
        results = client.cancel_orders()
        print(f"Cancelled {len(results)} order(s).")

else:
    print(__doc__)  # unknown command: print the help text at the top of this file
