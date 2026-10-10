"""
STEP 11 (rebuilt in Lesson 32): your stock dashboard.

Streamlit turns a normal Python script into a web page. Every st.something(...)
call adds a piece to the page: a title, a number, a chart, a table, a slider.
Whenever you click something, Streamlit re-runs this script from top to bottom.

Lesson 32 made it beginner-friendly:
  - a 🏠 Home tab that sums everything up in plain sentences
  - "What does this mean?" boxes and ⓘ tooltips everywhere
  - friendlier tables (progress bars, % signs, no raw column names)
  - a new 🏆 Top performers tab (past results + next month's risk range)

READ-ONLY: no button on this page buys or sells anything.
Start it with:   python -m streamlit run lessons/step11_dashboard.py   (opens at http://localhost:8501)
  ("python -m" makes sure the project's own Streamlit runs, not another copy on your Mac)

Coding ideas over the lessons: widgets, caching (11), fragments/polling (14), tabs and
separating calculations from display (21), session state (22), column_config (32).
"""

import os

import altair as alt
import pandas as pd
import streamlit as st
from alpaca.trading.requests import GetPortfolioHistoryRequest

from lab.currency import euro_strength, to_euro_prices
from lab.helpers import daily_closes, latest_session_minutes, latest_trade, trading_client
from lab.performers import PERIODS, POPULAR, top_performers
from lab.portfolio import health_check, mirror_status, simulate
from lab.report import market_overview
from lab.risk_forecast import forecast_holdings

LOG_FILE = "data/bot_log.csv"
PORTFOLIO_FILE = "my_portfolio.csv"
GREEN, RED = "#1a7f37", "#cf222e"

st.set_page_config(page_title="My Stock Dashboard", page_icon="📈", layout="wide")


# =============================== DATA (cached) ===============================
# CACHING: @st.cache_data remembers a function's answer for `ttl` seconds, so clicking
# around doesn't re-download everything. Inputs must be unchangeable (e.g. tuples).

@st.cache_data(ttl=60)
def load_account():
    client = trading_client()
    account = client.get_account()
    positions = pd.DataFrame([
        {"Stock": p.symbol, "Shares": float(p.qty), "Bought at": float(p.avg_entry_price),
         "Price now": float(p.current_price), "Value": float(p.market_value),
         "Profit $": float(p.unrealized_pl), "Profit %": float(p.unrealized_plpc) * 100}
        for p in client.get_all_positions()
    ])
    return account, positions, client.get_clock().is_open


@st.cache_data(ttl=300)
def load_equity(period):
    history = trading_client().get_portfolio_history(GetPortfolioHistoryRequest(period=period, timeframe="1D"))
    equity = pd.Series(history.equity, index=pd.to_datetime(history.timestamp, unit="s"))
    return equity[equity > 0]


@st.cache_data(ttl=600)
def load_health_check():
    return health_check()


@st.cache_data(ttl=3600)
def load_risk(values, in_euros=False):
    return forecast_holdings(dict(values), in_euros=in_euros)


@st.cache_data(ttl=3600)
def load_returns(symbols):
    return daily_closes(list(symbols), days=365).pct_change().dropna()


@st.cache_data(ttl=300)
def load_prices(symbol):
    return daily_closes(symbol, days=365 * 2)


@st.cache_data(ttl=900)
def load_market():
    return market_overview()


@st.cache_data(ttl=3600)
def load_performers(symbols, period_days, in_euros=False):
    closes = daily_closes(list(symbols), days=400, keep_gaps=True)
    if in_euros:  # Lesson 33: see the results the way a euro investor experiences them
        closes = to_euro_prices(closes, euro_strength())
    return top_performers(closes, period_days), closes


def load_real():
    """Your real holdings (private file). None if it doesn't exist yet."""
    return pd.read_csv(PORTFOLIO_FILE).set_index("symbol") if os.path.exists(PORTFOLIO_FILE) else None


# =============================== SMALL HELPERS ===============================

def explain(text, title="ℹ️ What does this mean?"):
    """A fold-out box with a plain-English explanation - closed until you click it."""
    with st.expander(title):
        st.markdown(text)


def money(x, sign=""):
    """'$' signs inside st.markdown need a backslash, or two of them become a maths formula (Lesson 11)."""
    return f"{sign}\\${abs(x):,.2f}" if sign else f"\\${x:,.2f}"


def line_chart(data, y_title="USD"):
    """Line chart whose y-axis fits the data (st.line_chart always starts at 0)."""
    long = data.reset_index(names="Date").melt("Date", var_name="Line", value_name=y_title)
    chart = alt.Chart(long).mark_line().encode(
        x=alt.X("Date:T", title=None),
        y=alt.Y(f"{y_title}:Q", scale=alt.Scale(zero=False)),
        color=alt.Color("Line:N", legend=alt.Legend(orient="top", title=None),
                        scale=alt.Scale(scheme="category10")),
        tooltip=["Date:T", "Line:N", alt.Tooltip(f"{y_title}:Q", format=",.2f")],
    )
    st.altair_chart(chart, width="stretch")


def up_down_bars(values, label):
    """Horizontal bars, green for up and red for down."""
    data = values.rename(label).rename_axis("Stock").reset_index()  # a one-column Series -> a table
    chart = alt.Chart(data).mark_bar().encode(
        y=alt.Y("Stock:N", sort="-x", title=None),
        x=alt.X(f"{label}:Q"),
        color=alt.condition(alt.datum[label] > 0, alt.value(GREEN), alt.value(RED)),
        tooltip=["Stock", alt.Tooltip(f"{label}:Q", format="+.1f")],
    )
    st.altair_chart(chart, width="stretch")


PCT = st.column_config.NumberColumn(format="%.1f%%")       # shows 12.3%
SIGNED_PCT = st.column_config.NumberColumn(format="%+.1f%%")
DOLLARS = st.column_config.NumberColumn(format="$%.2f")
EUROS = st.column_config.NumberColumn(format="€%.2f")


# =============================== PAGE HEADER & SIDEBAR ===============================

st.title("📈 My Stock Dashboard")
st.caption("A student learning project · the Alpaca account here is PAPER (practice) money · "
           "facts and risk ranges only - not financial advice")

with st.sidebar:
    st.header("⚙️ Settings")
    currency = st.radio("Show results in", ["€ euros", "$ dollars"], horizontal=True,
                        help="You invest in euros, but most holdings are priced in dollars. "
                             "Euros include the exchange rate - what your broker app shows.")
    in_euros = currency.startswith("€")
    live_on = st.toggle("Live price updates", value=True, help="Refresh the 📈 Live prices tab every 5 seconds.")
    if st.button("🔄 Refresh all data", width="stretch"):
        st.cache_data.clear()
    st.divider()
    st.header("📖 Word list")
    with st.expander("Open the word list"):
        st.markdown("""
- **Stock / share**: a small piece of one company.
- **ETF / fund**: one share that holds many companies at once (S&P 500 ≈ 500 US companies).
- **Paper account**: Alpaca's practice account with fake money.
- **Return**: how much something went up or down, in %.
- **Volatility (bumpiness)**: how much a price usually swings in a year. Higher = bumpier ride.
- **Typical month**: in about 2 months out of 3, the move stays within ± this.
- **Rough bad month**: about 1 month in 20 is worse than this.
- **Diversified**: money spread over many different things, so one bad one can't sink you.
- **Correlation**: how much two things move together (1 = always, 0 = unrelated).
- **Mirror**: the paper account copying your real holdings.
- **Exchange rate (EUR/USD)**: how many dollars one euro buys. When it falls, your US holdings are worth more in euros.
""")

real = load_real()
account, positions, market_open = load_account()

home_tab, mine_tab, top_tab, live_tab, paper_tab, whatif_tab = st.tabs([
    "🏠 Home", "💼 My portfolio", "🏆 Top performers", "📈 Live prices", "🧪 Paper account", "🔀 What-if"])


# =============================== 🏠 HOME ===============================
with home_tab:
    st.subheader("Your day at a glance")
    st.info("New here? This page sums everything up. Each tab above goes deeper - and every section "
            "has a **ℹ️ What does this mean?** box you can open.")

    market = load_market()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500 (USA)", f"{market.loc['SPY', 'day_%']:+.2f}%", "latest trading day",
              delta_color="off", delta_arrow="off", help="The 500 biggest US companies.")
    c2.metric("MSCI World (global)", f"{market.loc['URTH', 'day_%']:+.2f}%",
              "latest trading day", delta_color="off", delta_arrow="off",
              help="About 1,400 big companies from 23 countries.")
    c3.metric("US stock market", "Open 🟢" if market_open else "Closed 🔴",
              help="Regular hours: 15:30-22:00 Central European time, Monday-Friday.")
    c4.metric("Paper account (practice money)", f"${float(account.portfolio_value):,.0f}")

    if real is not None:
        total, profit = real["value_eur"].sum(), real["profit_eur"].sum()
        risk = load_risk(tuple(real["value_eur"].items()), in_euros)
        typical = risk[1].iloc[0]["typical_%"]
        perf, _ = load_performers(tuple(real.index), PERIODS["1 month"], in_euros)

        st.subheader("Your real portfolio")
        c1, c2, c3 = st.columns(3)
        c1.metric("Worth", f"€{total:,.2f}")
        c2.metric("Profit so far", f"€{profit:+,.2f}", f"{profit / (total - profit):+.1%}")
        c3.metric("Normal monthly swing", f"±{typical:.1f}%",
                  help="In about 2 months out of 3, your portfolio's monthly move stays within this range.")

        best, worst = perf.index[0], perf.index[-1]
        st.markdown(
            f"- 📅 **This month** (in {'euros' if in_euros else 'dollars'}) your best holding was **{best}** "
            f"({perf.loc[best, 'return_%']:+.1f}%) and your weakest was **{worst}** "
            f"({perf.loc[worst, 'return_%']:+.1f}%).\n"
            f"- 🎢 In a normal month your whole portfolio moves up or down by up to about "
            f"**{typical:.1f}%** - on €{total:,.0f}, that's about **€{total * typical / 100:,.0f}**.\n"
            f"- 🏦 The paper account holds **{len(positions)}** positions worth "
            f"{money(positions['Value'].sum()) if not positions.empty else money(0)} in total.")
    else:
        st.warning("Add your real holdings to **my_portfolio.csv** to see them here "
                   "(copy **my_portfolio.example.csv** to start).")

    explain("""
- **S&P 500 / MSCI World** are "the market" - big baskets of companies. If they're up, most stocks had a good day.
- **Normal monthly swing** is a *risk forecast*: it says how much your portfolio may move, **not which way**.
  This kind of forecast was tested in Lesson 28 and works reasonably well.
- Nothing on this dashboard predicts whether a price will go up. Lessons 23 and 28 tested that and found
  past winners don't predict future winners.
""")


# =============================== 💼 MY PORTFOLIO ===============================
with mine_tab:
    if real is None:
        st.info("No my_portfolio.csv yet - copy my_portfolio.example.csv and fill in your holdings.")
    else:
        total, profit = real["value_eur"].sum(), real["profit_eur"].sum()
        st.caption("From my_portfolio.csv - private, stays on your Mac, never uploaded")

        st.subheader("What you own")
        table = pd.DataFrame({
            "Name": real["name"],
            "Value": real["value_eur"],
            "Share of portfolio": real["value_eur"] / total * 100,
            "Profit €": real["profit_eur"],
            "Profit %": real["profit_eur"] / (real["value_eur"] - real["profit_eur"]) * 100,
        }).reset_index(names="Stock")
        st.dataframe(
            table, hide_index=True, width="stretch",
            column_config={
                "Value": EUROS,
                "Share of portfolio": st.column_config.ProgressColumn(
                    format="%.1f%%", min_value=0, max_value=float(table["Share of portfolio"].max()),
                    help="How much of your money is in this one holding."),
                "Profit €": st.column_config.NumberColumn(format="€%+.2f"),
                "Profit %": SIGNED_PCT,
            },
        )
        explain("""
- **Share of portfolio**: how much of your money sits in this holding. A long bar = a big bet on one company.
- **Profit**: today's value minus what you paid (from your file - update it when things change).
""")

        st.subheader("How much could each one swing next month?")
        per_holding, mix, left_out = load_risk(tuple(real["value_eur"].items()), in_euros)
        st.caption(f"Swings measured in {'euros (including the EUR/USD rate)' if in_euros else 'US dollars'} "
                   "- switch in the sidebar")
        m = mix.iloc[0]
        st.markdown(f"**Your whole portfolio:** in about **2 months out of 3** it moves less than "
                    f"**±{m['typical_%']:.1f}%**. Roughly **1 month in 20** is worse than **{m['bad_%']:.1f}%**.")
        st.dataframe(
            per_holding.reset_index(names="Stock").rename(columns={
                "volatility_%": "Bumpiness (per year)", "typical_%": "Typical month (±)",
                "bad_%": "Rough bad month"}),
            hide_index=True, width="stretch",
            column_config={"Bumpiness (per year)": PCT, "Typical month (±)": PCT, "Rough bad month": PCT},
        )
        if left_out:
            st.caption(f"No forecast for {', '.join(left_out)} (not enough price data).")
        explain("""
This is a **risk forecast** - how *much* prices may move, not *which way*.
- **Typical month**: in about 2 months out of 3, the move stays inside this range.
- **Rough bad month**: about 1 month in 20 is worse. Real markets can be wilder than this guide.
- Funds like the S&P 500 swing much less than single companies, because they hold hundreds of them.
""")

        st.subheader("Is the paper account a copy of this? (mirror)")
        paper = (positions.set_index("Stock")["Value"] if not positions.empty else pd.Series(dtype=float))
        status = mirror_status(paper, real["value_eur"])
        cant = [x for x in left_out if x in status.index and status.loc[x, "paper_$"] == 0]
        status.loc[cant, "status"] = "can't mirror"
        mirrorable = len(real) - len(cant)
        in_sync = int((status["status"] == "in sync").sum())
        st.progress(in_sync / mirrorable, text=f"{in_sync} of {mirrorable} holdings match")
        if in_sync == mirrorable and not (status["status"] == "extra").any():
            st.success("The paper account matches your real portfolio. ✅")
        else:
            st.warning("Not matching yet. To fix: pause the paper bot, then run "
                       "`python lessons/step30_mirror.py --trade` in the terminal.")
        st.dataframe(
            status.reset_index(names="Stock").rename(columns={
                "real_$": "Real", "paper_$": "Paper", "difference_$": "Difference", "status": "Status"}),
            hide_index=True, width="stretch",
            column_config={"Real": DOLLARS, "Paper": DOLLARS,
                           "Difference": st.column_config.NumberColumn(format="$%+.2f")},
        )
        explain("""
The paper (practice) account can **copy** your real holdings (Lesson 30), using €1 = \\$1.
- **in sync**: within 5% of the real amount · **too much / too little**: needs resizing
- **extra**: in the paper account but not in your real portfolio · **can't mirror**: no price data
""")


# =============================== 🏆 TOP PERFORMERS ===============================
with top_tab:
    st.subheader("Who did best?")
    c1, c2 = st.columns(2)
    group = c1.radio("Which stocks?", ["My holdings", "Popular US stocks & funds"], horizontal=True,
                     disabled=real is None, index=0 if real is not None else 1)
    period = c2.select_slider("Over the last…", options=list(PERIODS), value="1 month")
    symbols = tuple(real.index) if (group == "My holdings" and real is not None) else tuple(POPULAR)

    perf, closes = load_performers(symbols, PERIODS[period], in_euros)
    st.caption(f"Returns in {'euros - including the exchange rate, like your broker app' if in_euros else 'US dollars'} "
               "· switch in the sidebar")
    if perf.empty:
        st.info("Not enough price data for this period.")
    else:
        st.markdown(f"#### 🥇 Top 3 over the last {period}")
        for col, (sym, r) in zip(st.columns(3), perf.head(3).iterrows()):
            col.metric(sym, f"{r['return_%']:+.1f}%", f"next month: ±{r['typical_%']:.1f}% typical swing",
                       delta_color="off", delta_arrow="off",
                       help=f"Rough bad month: {r['bad_%']:.1f}%. A range, not a direction.")

        st.warning(f"**A past winner is not a prediction.** In this project's own tests, last period's best "
                   f"stocks told us nothing about the next period (rank correlation about 0.00, Lessons 23 & 28). "
                   f"The swing ranges below are the only forecast that held up - they say how much a stock "
                   f"may move, not which way.")

        left, right = st.columns([1, 1])
        with left:
            st.markdown(f"**Return over the last {period}** (all {len(perf)})")
            up_down_bars(perf["return_%"], "Return %")
        with right:
            st.markdown("**Top 5: price path** (start = 100)")
            days = PERIODS[period]
            top5 = closes[perf.index[:5]].dropna(how="all").iloc[-days - 1:]
            line_chart(top5 / top5.iloc[0] * 100, y_title="Start = 100")

        st.dataframe(
            perf.reset_index(names="Stock").rename(columns={
                "return_%": f"Return ({period})", "volatility_%": "Bumpiness (per year)",
                "typical_%": "Next month: typical swing (±)", "bad_%": "Next month: rough bad month"}),
            hide_index=True, width="stretch",
            column_config={f"Return ({period})": SIGNED_PCT, "Bumpiness (per year)": PCT,
                           "Next month: typical swing (±)": PCT, "Next month: rough bad month": PCT},
        )
        explain("""
- **Return**: how much the price went up or down over the period you picked - a fact about the past.
- **Next month: typical swing**: the risk forecast. Big winners are often also the bumpiest stocks -
  a +40% month usually comes with big swings in both directions.
- **€ or $?** In euros, a weaker euro makes US stocks worth more to you, and a stronger euro worth
  less - so the same stock can show a different return. Switch in the sidebar to compare (Lesson 33).
- **Why no "will it go up?" forecast?** Lessons 23 and 28 tested that idea on years of data: the order of
  winners and losers kept reshuffling, so a prediction would just be a guess.
""")


# =============================== 📈 LIVE PRICES ===============================
with live_tab:
    c1, c2 = st.columns([1, 2])
    symbol = c1.text_input("Stock or fund symbol", "SPY",
                           help="e.g. AAPL (Apple), NVDA (Nvidia), SPY (S&P 500 fund)").strip().upper()
    ma_days = c2.slider("Trend line: average of the last … days", 10, 200, 50, 5,
                        help="A moving average smooths out daily ups and downs to show the trend.")

    def live_section():
        # A FRAGMENT re-runs on its own every 5 seconds (POLLING, Lesson 14).
        try:
            minutes = latest_session_minutes(symbol)
            trade = latest_trade(symbol)
        except Exception as error:
            st.error(f"Couldn't load live data for '{symbol}'. Check the symbol. ({error})")
            return
        session_open = minutes["open"].iloc[0]
        change = trade.price - session_open
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Latest price", f"${trade.price:,.2f}", f"{change / session_open * 100:+.2f}% since the open")
        c2.metric("Today's high", f"${minutes['high'].max():,.2f}")
        c3.metric("Today's low", f"${minutes['low'].min():,.2f}")
        c4.metric("Last trade (your time)", f"{trade.timestamp.astimezone():%H:%M:%S}")
        line_chart(minutes[["close"]].rename(columns={"close": f"{symbol}, minute by minute"})
                   .tz_localize(None), y_title="Price $")
        st.caption(f"Trading day of {minutes.index[0]:%A %d %B} · chart times are New York time · "
                   f"{'updates every 5 seconds' if live_on else 'live updates off'}"
                   + ("" if market_open else " · the market is closed, so this is the last trading day"))

    st.subheader(f"🔴 {symbol} today")
    st.fragment(run_every="5s" if live_on else None)(live_section)()

    st.subheader(f"{symbol} over two years, with its {ma_days}-day trend line")
    try:
        close = load_prices(symbol)
        chart = pd.DataFrame({"Price": close, f"{ma_days}-day average": close.rolling(ma_days).mean()})
        line_chart(chart, y_title="Price $")
        last, avg = chart.iloc[-1, 0], chart.iloc[-1, 1]
        trend = "above" if last > avg else "below"
        st.markdown(f"The price ({money(last)}) is **{trend}** its {ma_days}-day average ({money(avg)}).")
    except Exception as error:
        st.error(f"Couldn't load prices for '{symbol}'. ({error})")
    explain(f"""
- The **minute-by-minute chart** shows today's trading. Prices come from the free IEX feed.
- The **trend line** is the average price of the last {ma_days} trading days. Price above the line
  means it has been rising lately; below means falling. It describes the past - it doesn't predict.
""")


# =============================== 🧪 PAPER ACCOUNT ===============================
with paper_tab:
    st.caption("Alpaca's practice account - fake money, used by the bots and the mirror")
    history_period = st.segmented_control(
        "Show the last…", ["1W", "1M", "3M", "6M", "1A"], default="1M",
        format_func={"1W": "week", "1M": "month", "3M": "3 months", "6M": "6 months", "1A": "year"}.get)
    equity = load_equity(history_period or "1M")
    value = float(account.portfolio_value)
    c1, c2, c3 = st.columns(3)
    c1.metric("Account value", f"${value:,.0f}", f"{value - float(account.last_equity):+,.2f} today")
    c2.metric("Cash (not invested)", f"${float(account.cash):,.0f}")
    c3.metric("Change over this period", f"{(equity.iloc[-1] / equity.iloc[0] - 1) * 100:+.2f}%")
    line_chart(equity.rename("Account value").to_frame(), y_title="Value $")

    st.subheader("What the paper account owns")
    if positions.empty:
        st.info("No positions yet.")
    else:
        st.dataframe(positions, hide_index=True, width="stretch", column_config={
            "Bought at": DOLLARS, "Price now": DOLLARS, "Value": DOLLARS,
            "Profit $": st.column_config.NumberColumn(format="$%+.2f"), "Profit %": SIGNED_PCT})

    check = load_health_check()
    if check is not None:
        st.subheader("Where is the risk?")
        bars = (check.positions[["money_%", "risk_%"]]
                .rename(columns={"money_%": "Share of money", "risk_%": "Share of risk"})
                .reset_index(names="Stock").melt("Stock", var_name="Measure", value_name="Percent"))
        st.altair_chart(alt.Chart(bars).mark_bar().encode(
            y=alt.Y("Stock:N", sort=list(check.positions.index), title=None),
            x=alt.X("Percent:Q", title="%"), yOffset="Measure:N",
            color=alt.Color("Measure:N", legend=alt.Legend(orient="top", title=None),
                            scale=alt.Scale(scheme="category10")),
            tooltip=["Stock", "Measure", alt.Tooltip("Percent:Q", format=".1f")]), width="stretch")
        c1, c2 = st.columns(2)
        c1.metric("Acts like this many equal-sized holdings", f"{check.effective:.1f}",
                  help="'Effective number of stocks': 10 holdings where one is 90% acts like about 1.")
        if not check.close_pairs.empty:
            (a, b), corr = next(iter(check.close_pairs.items()))
            c2.metric("Most alike pair", f"{a} & {b}", f"move together {corr:.2f} (1 = always)",
                      delta_color="off", delta_arrow="off")
        explain("""
- **Share of money vs share of risk**: a calm fund can be lots of your money but little of your risk;
  a bumpy stock can be a little money but lots of risk.
- **Acts like … equal-sized holdings**: a quick way to see how spread out the money really is.
""")

    st.subheader("Bot decisions (newest first)")
    if os.path.exists(LOG_FILE):
        st.dataframe(pd.read_csv(LOG_FILE).iloc[::-1].head(20), hide_index=True, width="stretch")
    else:
        st.info("No bot log yet.")


# =============================== 🔀 WHAT-IF ===============================
# SESSION STATE (Lesson 22): st.session_state survives re-runs, so sliders keep their values
# and the reset button can put them back.
with whatif_tab:
    st.subheader("What if the paper account had a different mix?")
    st.caption("Drag the sliders. Uses the past year of prices: it shows what WOULD have happened, not a forecast.")
    check = load_health_check()
    if check is None:
        st.info("No stock positions in your paper account yet.")
    else:
        current = check.positions["money_%"].round(1)
        extra = st.text_input("Add stocks to try (comma-separated)", "KO, XOM",
                              help="They start at 0%. Drag their slider up to add them.")
        extras = [x.strip().upper() for x in extra.split(",") if x.strip() and x.strip().upper() not in current.index]
        syms = list(current.index) + extras
        defaults = {**current.to_dict(), **{x: 0.0 for x in extras}}
        if st.button("↩️ Back to the current mix"):
            for s, v in defaults.items():
                st.session_state[f"w_{s}"] = v
        cols = st.columns(4)
        sliders = {}
        for i, s in enumerate(syms):
            key = f"w_{s}"
            if key not in st.session_state:
                st.session_state[key] = defaults[s]
            sliders[s] = cols[i % 4].slider(f"{s} %", 0.0, 100.0, step=0.5, key=key)

        total = sum(sliders.values())
        if total == 0:
            st.warning("Move at least one slider above zero.")
        else:
            try:
                returns = load_returns(tuple(sorted(syms)))
                before, after = simulate(returns, current), simulate(returns, sliders)
            except KeyError as error:
                st.error(f"No price data for {error} - check the symbol.")
            else:
                def vs_now(key, unit="", decimals=1):
                    change = round(after[key] - before[key], decimals)
                    return None if change == 0 else f"{change:+.{decimals}f}{unit} vs now"

                m1, m2, m3 = st.columns(3)
                m1.metric("$100 would have become", f"${after['$100 became']:.2f}", vs_now("$100 became", decimals=2))
                m2.metric("Bumpiness (per year)", f"{after['volatility_%']:.1f}%", vs_now("volatility_%", " pts"),
                          delta_color="inverse", help="Lower is calmer - so going down shows green.")
                m3.metric("Worst drop along the way", f"{after['biggest_drop_%']:.1f}%",
                          vs_now("biggest_drop_%", " pts"))
                line_chart(pd.DataFrame({"Current mix": before["growth"], "What-if mix": after["growth"]}),
                           y_title="Value of $100")
                explain("""
This replays the **past year** with your slider mix. It's hindsight: good for seeing how *calm or bumpy*
a mix is (that tends to carry over), not for picking winners (that doesn't - Lesson 23).
""")
