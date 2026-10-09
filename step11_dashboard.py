"""
STEP 11: A web dashboard for your project.

Streamlit turns a normal Python script into a web page. Every st.something(...)
call adds a piece to the page: a title, a number, a chart, a table, a slider.
Whenever you move a slider or click a button, Streamlit re-runs this script
from top to bottom and redraws the page.

This dashboard is READ-ONLY: it shows your paper account but has no buttons
that place orders. Trading stays in step7 / step8, where you confirm things.

Start it with:   streamlit run step11_dashboard.py
It opens in your browser at http://localhost:8501   (Ctrl+C in the terminal stops it)

New coding ideas in this lesson:
  - a web page made from Python (no HTML needed)
  - CACHING: remember downloaded data for a while instead of re-downloading on every click
  - WIDGETS: sliders, text boxes and buttons that feed values into your code
"""

import os

import altair as alt
import pandas as pd
import streamlit as st
from alpaca.trading.requests import GetPortfolioHistoryRequest

from helpers import daily_closes, latest_session_minutes, latest_trade, trading_client

LOG_FILE = "data/bot_log.csv"

st.set_page_config(page_title="My Paper Trading Dashboard", page_icon="📈", layout="wide")
st.title("📈 My Paper Trading Dashboard")
st.caption("Paper account (fake money) · student learning project · not financial advice")


# --- CACHING: @st.cache_data remembers a function's answer for `ttl` seconds ----
# Without it, every slider move would re-download everything from Alpaca.
@st.cache_data(ttl=60)
def load_account():
    client = trading_client()
    account = client.get_account()
    positions = [
        {
            "Symbol": p.symbol,
            "Shares": float(p.qty),
            "Bought at $": float(p.avg_entry_price),
            "Now $": float(p.current_price),
            "Value $": float(p.market_value),
            "Profit/loss $": float(p.unrealized_pl),
            "Profit/loss %": float(p.unrealized_plpc) * 100,
        }
        for p in client.get_all_positions()
    ]
    return account, pd.DataFrame(positions), client.get_clock().is_open


@st.cache_data(ttl=300)
def load_equity(period):
    history = trading_client().get_portfolio_history(
        GetPortfolioHistoryRequest(period=period, timeframe="1D")
    )
    equity = pd.Series(history.equity, index=pd.to_datetime(history.timestamp, unit="s"))
    return equity[equity > 0]


@st.cache_data(ttl=300)
def load_prices(symbol):
    return daily_closes(symbol, days=365 * 2)


def line_chart(data, y_title="USD"):
    """
    Line chart whose y-axis fits the data instead of starting at 0.
    (st.line_chart always starts at 0, which makes a $100,000 account
    moving by $100 look like a perfectly flat line.)
    """
    long = data.reset_index(names="Date").melt("Date", var_name="Line", value_name=y_title)
    chart = alt.Chart(long).mark_line().encode(
        x="Date:T",
        y=alt.Y(f"{y_title}:Q", scale=alt.Scale(zero=False)),
        color=alt.Color("Line:N", legend=alt.Legend(orient="top", title=None)),
        tooltip=["Date:T", "Line:N", alt.Tooltip(f"{y_title}:Q", format=",.2f")],
    )
    st.altair_chart(chart, width="stretch")


# --- Sidebar: the WIDGETS ----------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    symbol = st.text_input("Stock to chart", "SPY").strip().upper()
    ma_days = st.slider("Moving-average days", min_value=10, max_value=200, value=50, step=5)
    period = st.selectbox("Account history", ["1W", "1M", "3M", "6M", "1A"], index=1)
    live_on = st.toggle("Live updates (every 5 s)", value=True)
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()  # forget everything cached, download fresh


# --- LESSON 14: the live section ------------------------------------------------------
# A FRAGMENT is a piece of the page that can re-run ON ITS OWN. With run_every="5s",
# only this function re-runs every 5 seconds; the rest of the page stays still.
#
# This is POLLING (asking "anything new?" every 5 s), not streaming like Lesson 13.
# Why? The free plan allows ONE stream at a time, and a web page that re-runs on every
# click would easily open duplicates. Asking every 5 seconds is simple and reliable.
def live_section():
    try:
        minutes = latest_session_minutes(symbol)
        trade = latest_trade(symbol)
    except Exception as error:
        st.error(f"Couldn't load live data for '{symbol}': {error}")
        return

    session_open = minutes["open"].iloc[0]
    change = trade.price - session_open
    trade_time = trade.timestamp.astimezone()  # your local time

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{symbol} last trade", f"${trade.price:,.2f}",
              f"{change:+.2f} ({change / session_open * 100:+.2f}%) since open")
    # One $ per box: two $ signs in one box would be read as a maths formula (Lesson 11)
    c2.metric("Today's high", f"${minutes['high'].max():,.2f}")
    c3.metric("Today's low", f"${minutes['low'].min():,.2f}")
    c4.metric("Last trade at", f"{trade_time:%H:%M:%S}")

    chart = minutes[["close"]].rename(columns={"close": f"{symbol} 1-minute close"})
    line_chart(chart.tz_localize(None))  # New York time on the axis
    st.caption(f"Session of {minutes.index[0]:%A %d %B} · times on the chart are New York time · "
               f"{'refreshing every 5 s' if live_on else 'live updates off'} · free IEX feed")


st.subheader(f"🔴 Live: {symbol} today")
st.fragment(run_every="5s" if live_on else None)(live_section)()

# --- Section 1: account summary ---------------------------------------------------
account, positions, market_open = load_account()
equity = load_equity(period)

value = float(account.portfolio_value)
day_change = value - float(account.last_equity)  # last_equity = value at yesterday's close

col1, col2, col3, col4 = st.columns(4)
col1.metric("Account value", f"${value:,.0f}", f"{day_change:+,.2f} today")
col2.metric("Cash", f"${float(account.cash):,.0f}")
col3.metric(f"Change over {period}", f"{(equity.iloc[-1] / equity.iloc[0] - 1) * 100:+.2f}%")
col4.metric("Market", "Open" if market_open else "Closed")

st.subheader(f"Account value - last {period}")
line_chart(equity.rename("Account value").to_frame())

# --- Section 2: positions ---------------------------------------------------------
st.subheader("What you own")
if positions.empty:
    st.info("No positions yet.")
else:
    st.dataframe(
        positions.style.format(precision=2).map(
            lambda v: "color: green" if v > 0 else "color: red",
            subset=["Profit/loss $", "Profit/loss %"],
        ),
        hide_index=True,
        width="stretch",
    )

# --- Section 3: a stock with the moving-average rule ------------------------------
st.subheader(f"{symbol} and its {ma_days}-day average")
try:
    close = load_prices(symbol)
    chart = pd.DataFrame({"Close": close, f"{ma_days}-day average": close.rolling(ma_days).mean()})
    line_chart(chart)

    last_close, last_ma = chart.iloc[-1, 0], chart.iloc[-1, 1]
    if last_close > last_ma:
        # "\\$" = a plain dollar sign. Two bare $ signs would be read as a maths formula.
        st.success(f"Rule says **OWN**: \\${last_close:.2f} is above the average (\\${last_ma:.2f}).")
    else:
        st.warning(f"Rule says **CASH**: \\${last_close:.2f} is below the average (\\${last_ma:.2f}).")
except Exception as error:
    st.error(f"Couldn't load prices for '{symbol}': {error}")

# --- Section 4: the bot's log -----------------------------------------------------
st.subheader("Bot decisions (newest first)")
if os.path.exists(LOG_FILE):
    log = pd.read_csv(LOG_FILE)
    st.dataframe(log.iloc[::-1].head(20), hide_index=True, width="stretch")
else:
    st.info("No bot log yet - run `python step8_bot.py` first.")
