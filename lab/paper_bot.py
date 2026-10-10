"""
paper_bot.py - the decision logic for the paper-trading bot (Lesson 27).

PAPER MONEY ONLY: the bot trades Alpaca's practice account. Its decisions are an
experiment with a simple rule - not recommendations for real money. (In Lessons 5-6
this exact rule did WORSE than simply buying and holding.)

For each stock on the watchlist, the rule says OWN or CASH, and we compare that with
what the paper account holds right now:

    rule says   we hold it?   ->  action
    OWN         no                BUY       (buy about BUDGET dollars of it)
    OWN         yes               HOLD      (keep it)
    CASH        yes               SELL      (sell all of it)
    CASH        no                STAY OUT  (do nothing)
    (anything)  order waiting     WAIT      (an order is already pending - don't double up)
"""

import math

BUY, HOLD, SELL, STAY_OUT, WAIT = "BUY", "HOLD", "SELL", "STAY OUT", "WAIT"


def decide(rule_says_own, shares_held, order_pending):
    """The table above, as code."""
    if order_pending:
        return WAIT
    if rule_says_own:
        return HOLD if shares_held > 0 else BUY
    return SELL if shares_held > 0 else STAY_OUT


def shares_for(budget, price):
    """How many WHOLE shares the budget buys (0 if one share costs more than the budget)."""
    return math.floor(budget / price) if price > 0 else 0


def trend_rule(close, ma_days=50):
    """
    Lesson 5's rule, using finished days only:
    OWN if the last close is above its `ma_days`-day average.
    Returns (rule_says_own, last_close, average).
    """
    average = close.rolling(ma_days).mean().iloc[-1]
    last = close.iloc[-1]
    return bool(last > average), float(last), float(average)
