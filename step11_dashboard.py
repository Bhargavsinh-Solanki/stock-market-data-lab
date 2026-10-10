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
from portfolio import health_check, mirror_status, simulate
from risk_forecast import forecast_holdings

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


@st.cache_data(ttl=600)
def load_health_check():
    return health_check()  # the same calculations as step20, shared via portfolio.py


@st.cache_data(ttl=3600)
def load_risk(values):
    """Next month's risk for your real holdings. `values` is a tuple of (symbol, €) pairs,
    because cached inputs must be unchangeable."""
    return forecast_holdings(dict(values))


@st.cache_data(ttl=3600)
def load_returns(symbols):
    """A year of daily returns. `symbols` is a tuple, because cached inputs must be unchangeable."""
    return daily_closes(list(symbols), days=365).pct_change().dropna()


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
        # "category10" = clearly different colours per line (the default blues look alike)
        color=alt.Color("Line:N", legend=alt.Legend(orient="top", title=None),
                        scale=alt.Scale(scheme="category10")),
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


# --- LESSON 21: TABS - separate pages inside one app -----------------------------------
# Streamlit runs the code for EVERY tab on each refresh, so the slow health check is cached.
overview_tab, health_tab, whatif_tab, mine_tab = st.tabs(
    ["📊 Overview", "🩺 Portfolio health", "🧪 What-if", "💼 My real portfolio"])

with overview_tab:
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


# --- The Portfolio health tab (Lesson 21) -----------------------------------------------
with health_tab:
    st.caption("Read-only analysis of your paper portfolio using the past year of prices · "
               "educational, not financial advice · refreshes every 10 minutes")
    check = load_health_check()
    if check is None:
        st.info("No stock positions in your paper account yet.")
    else:
        cash = check.total - check.invested
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invested", f"${check.invested:,.0f}", f"{check.invested / check.total:.0%} of account",
                  delta_color="off", delta_arrow="off")
        c2.metric("Cash", f"${cash:,.0f}", f"{cash / check.total:.0%} of account",
                  delta_color="off", delta_arrow="off")
        c3.metric("Positions", len(check.positions))
        c4.metric("Effective number of stocks", f"{check.effective:.1f}",
                  help="How many equal-sized positions your portfolio really behaves like.")

        st.subheader("Share of money vs share of risk")
        bars = (check.positions[["money_%", "risk_%"]]
                .rename(columns={"money_%": "Share of money", "risk_%": "Share of risk"})
                .reset_index(names="Stock")
                .melt("Stock", var_name="Measure", value_name="Percent"))
        st.altair_chart(
            alt.Chart(bars).mark_bar().encode(
                y=alt.Y("Stock:N", sort=list(check.positions.index), title=None),
                x=alt.X("Percent:Q", title="%"),
                yOffset="Measure:N",  # two bars side by side for each stock
                color=alt.Color("Measure:N", legend=alt.Legend(orient="top", title=None),
                                scale=alt.Scale(scheme="category10")),
                tooltip=["Stock", "Measure", alt.Tooltip("Percent:Q", format=".1f")],
            ),
            width="stretch",
        )
        risky = check.positions[check.positions["risk_%"] > 1.5 * check.positions["money_%"]]
        if len(risky):
            st.warning("Carrying more than 1.5x their share of the risk: " + ", ".join(
                f"**{s}** ({r['money_%']:.1f}% of money, {r['risk_%']:.1f}% of risk)"
                for s, r in risky.iterrows()))

        st.dataframe(
            check.positions.rename(columns={
                "sector": "Sector", "value_$": "Value $", "money_%": "Money %",
                "risk_%": "Risk %", "own_volatility_%": "Own volatility %",
            }).style.format(precision=1),
            width="stretch",
        )

        left, right = st.columns(2)
        with left:
            st.subheader("By sector")
            st.bar_chart(check.by_sector, horizontal=True, x_label="", y_label="% of invested money")
        with right:
            st.subheader("Hidden overlap")
            if check.close_pairs.empty:
                st.success("No two holdings move together closely (correlation above 0.7).")
            for (a, b), c in check.close_pairs.items():
                st.info(f"**{a}** and **{b}** move together closely (correlation {c:.2f}).")

        st.subheader("Past year: today's mix vs just owning SPY")
        line_chart(check.growth, y_title="Value of $100")
        st.dataframe(
            check.comparison.rename(columns={
                "$100 became": "$100 became", "volatility_%": "Volatility %",
                "biggest_drop_%": "Biggest drop %",
            }).style.format(precision=1),
            width="stretch",
        )


# --- The What-if tab (Lesson 22) -----------------------------------------------------
# SESSION STATE: st.session_state is a dictionary that SURVIVES re-runs. Normally every
# variable is forgotten each time the script re-runs; anything in session_state is kept.
# Each slider stores its value there (under key="w_SYMBOL"), so the reset button can
# put them all back to your real mix.
with whatif_tab:
    st.caption("Drag the sliders to try a different mix. Uses the past year of prices, so it shows "
               "what WOULD have happened (hindsight), not a forecast · educational, not financial advice")
    check = load_health_check()
    if check is None:
        st.info("No stock positions in your paper account yet.")
    else:
        current = check.positions["money_%"].round(1)
        extra = st.text_input("Add stocks to try (comma-separated)", "KO, XOM",
                              help="They start at 0%. Drag their slider up to add them to the mix.")
        extras = [x.strip().upper() for x in extra.split(",")
                  if x.strip() and x.strip().upper() not in current.index]
        symbols = list(current.index) + extras
        defaults = {**current.to_dict(), **{x: 0.0 for x in extras}}

        if st.button("↩️ Back to my current mix"):
            for symbol_, value in defaults.items():
                st.session_state[f"w_{symbol_}"] = value

        columns = st.columns(4)
        sliders = {}
        for i, symbol_ in enumerate(symbols):
            key = f"w_{symbol_}"
            if key not in st.session_state:          # first time we see this stock
                st.session_state[key] = defaults[symbol_]
            sliders[symbol_] = columns[i % 4].slider(f"{symbol_} %", 0.0, 100.0, step=0.5, key=key)

        total = sum(sliders.values())
        if total == 0:
            st.warning("Move at least one slider above zero.")
        else:
            if abs(total - 100) > 0.5:
                st.caption(f"Sliders add up to {total:.1f}% - they're scaled to 100% for the maths.")
            try:
                returns = load_returns(tuple(sorted(symbols)))
                before, after = simulate(returns, current), simulate(returns, sliders)
            except KeyError as error:
                st.error(f"No price data for {error} - check the symbol.")
            else:
                def vs_now(key, unit="", decimals=1):
                    """The change badge, or None (no badge) if it rounds to zero.
                    Tiny leftovers like 0.0000001 would otherwise show as a red '+0.0'."""
                    change = round(after[key] - before[key], decimals)
                    return None if change == 0 else f"{change:+.{decimals}f}{unit} vs now"

                st.subheader("What-if mix vs your current mix (past year)")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("$100 became", f"${after['$100 became']:.2f}", vs_now("$100 became", decimals=2))
                m2.metric("Volatility", f"{after['volatility_%']:.1f}%", vs_now("volatility_%", " pts"),
                          delta_color="inverse")  # inverse: going DOWN is shown in green
                m3.metric("Biggest drop", f"{after['biggest_drop_%']:.1f}%", vs_now("biggest_drop_%", " pts"))
                m4.metric("Effective number of stocks", f"{after['effective_stocks']:.1f}",
                          vs_now("effective_stocks"))

                line_chart(pd.DataFrame({"Current mix": before["growth"],
                                         "What-if mix": after["growth"]}), y_title="Value of $100")

                mix = pd.DataFrame({"Money %": pd.Series(sliders) / total * 100,
                                    "Risk %": after["risk_%"]}).fillna(0)
                st.dataframe(mix[mix["Money %"] > 0].sort_values("Money %", ascending=False)
                             .style.format(precision=1), width="stretch")


# --- The "My real portfolio" tab (Lesson 31) ---------------------------------------------
# Brings Lessons 24 (profit), 28 (risk forecast) and 30 (mirror check) together on one page.
# my_portfolio.csv never leaves your Mac: the dashboard runs locally (localhost).
with mine_tab:
    if not os.path.exists("my_portfolio.csv"):
        st.info("No my_portfolio.csv yet - copy my_portfolio.example.csv and fill in your holdings.")
    else:
        real = pd.read_csv("my_portfolio.csv").set_index("symbol")
        total, profit = real["value_eur"].sum(), real["profit_eur"].sum()
        paid = total - profit
        st.caption("Your real holdings from my_portfolio.csv (private, never uploaded) · "
                   "facts only, not financial advice")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total value", f"€{total:,.2f}")
        c2.metric("Profit", f"€{profit:+,.2f}", f"{profit / paid:+.1%} on €{paid:,.0f} paid")
        c3.metric("Holdings", len(real))
        risk = load_risk(tuple(real["value_eur"].items()))
        c4.metric("Typical month (2 in 3)", f"±{risk[1].iloc[0]['typical_%']:.1f}%",
                  help="Lesson 28's risk forecast for the whole mix: how much it may swing, not which way.")

        table = real.assign(
            share_pct=real["value_eur"] / total * 100,
            profit_pct=real["profit_eur"] / (real["value_eur"] - real["profit_eur"]) * 100,
        ).rename(columns={"name": "Name", "value_eur": "Value €", "profit_eur": "Profit €",
                          "share_pct": "Share %", "profit_pct": "Profit %"})
        st.dataframe(
            table.style.format(precision=1).map(
                lambda v: "color: green" if v > 0 else "color: red" if v < 0 else "",
                subset=["Profit €", "Profit %"]),
            width="stretch",
        )

        st.subheader("Next month's normal range")
        per_holding, mix, left_out = risk
        st.write(f"Whole mix: in about **2 months out of 3** the move stays within "
                 f"**±{mix.iloc[0]['typical_%']:.1f}%**; roughly **1 month in 20** is worse than "
                 f"**{mix.iloc[0]['bad_%']:.1f}%**. How much it may swing - not which way.")
        st.dataframe(per_holding.rename(columns={
            "volatility_%": "Volatility / year %", "typical_%": "Typical month ±%",
            "bad_%": "Rough bad month %"}).style.format(precision=1), width="stretch")
        if left_out:
            st.caption(f"No forecast (too little price history): {', '.join(left_out)}")

        st.subheader("Paper account mirror (Lesson 30)")
        _, paper_positions, _ = load_account()
        paper = (paper_positions.set_index("Symbol")["Value $"] if not paper_positions.empty
                 else pd.Series(dtype=float))
        status = mirror_status(paper, real["value_eur"])
        # Holdings with no price data (e.g. Bayer) can't be mirrored automatically (Lesson 30)
        cant = [x for x in left_out if x in status.index and status.loc[x, "paper_$"] == 0]
        status.loc[cant, "status"] = "can't mirror"
        mirrorable = len(real) - len(cant)
        in_sync = (status["status"] == "in sync").sum()
        if in_sync == mirrorable and not (status["status"] == "extra").any():
            st.success(f"All {mirrorable} mirrorable holdings are in sync (within 5%, €1 = $1).")
        else:
            st.warning(f"{in_sync} of {mirrorable} holdings in sync. To fix: pause the paper bot, then run "
                       "`python step30_mirror.py --trade`.")
        if cant:
            st.caption(f"Can't be mirrored automatically (no price data): {', '.join(cant)}")
        st.dataframe(
            status.rename(columns={"real_$": "Real (€ as $)", "paper_$": "Paper $",
                                   "difference_$": "Difference $", "status": "Status"})
            .style.format(precision=2).map(
                lambda v: "color: green" if v == "in sync" else "color: orange", subset=["Status"]),
            width="stretch",
        )
