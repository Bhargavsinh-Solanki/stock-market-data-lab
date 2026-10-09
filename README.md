# Stock Market Data Lab

[![tests](https://github.com/Bhargavsinh-Solanki/global-political-trades-forecast/actions/workflows/tests.yml/badge.svg)](https://github.com/Bhargavsinh-Solanki/global-political-trades-forecast/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.14-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A hands-on learning project that uses the **[Alpaca](https://alpaca.markets) API** to fetch
live and historical stock market data, test trading rules honestly, run a paper-trading bot,
and show it all on a live web dashboard.

It's built as **14 small, heavily commented lessons**, each one adding a new coding idea.

> ⚠️ Educational project only. Paper trading (fake money). Not financial advice.

---

## What it does

| Area | Highlights |
|---|---|
| **Market data** | Historical daily and 1-minute bars, latest trades, news headlines, live websocket stream |
| **Analysis** | Returns, volatility, max drawdown, moving averages, news vs price-move correlation |
| **Backtesting** | Moving-average strategy vs buy & hold, trading costs, train/test split to expose overfitting |
| **Paper trading** | Market and limit orders, a dry-run-first bot with a watchlist and decision log |
| **Dashboard** | Streamlit app with live-updating intraday chart, account value, positions and bot log |
| **Engineering** | Shared `helpers` module, unit tests with pytest, CI on GitHub Actions |

## Key findings

These are real results from this project's own data (Oct 2023 – Oct 2026):

1. **A simple trend-following rule didn't beat buy & hold.** On 5 stocks over 3 years, it lost to
   simply holding every time, although it did reduce the worst drops (SPY: −9% vs −19%).
2. **Optimising settings creates false confidence.** The best Tesla setting on training data
   turned $100 into $354. On unseen data, the same setting turned $100 into $76.
   **0 of 39** settings beat buy & hold out-of-sample.
3. **News days are bigger move days, but that doesn't prove news causes the moves.**
   On the busiest 20% of news days, AAPL and TSLA moved about 1.6–1.8× as much (correlation +0.38).

<table>
<tr>
<td><img src="docs/images/backtest.png" alt="SPY backtest: moving-average rule vs buy and hold"></td>
<td><img src="docs/images/overfitting.png" alt="TSLA: best setting on training data fails on test data"></td>
</tr>
<tr>
<td><img src="docs/images/compare.png" alt="Growth of $100 in AAPL, MSFT, TSLA and SPY"></td>
<td><img src="docs/images/news.png" alt="AAPL news stories per day vs daily price move"></td>
</tr>
</table>

## Things I was careful about

- **No look-ahead bias.** Signals act the *next* day (`shift(1)`), and news published after the
  16:00 New York close is matched to the next trading day. Both are covered by unit tests.
- **Trading costs** are included in backtests (0.1% per switch).
- **Out-of-sample testing.** Strategy settings are chosen on old data and judged on newer data.
- **Safety.** All trading code is locked to the paper account. The bot dry-runs by default and only
  touches symbols on its watchlist. API keys stay in `.env`, which is never committed.

---

## Getting started

You need Python 3.12+ and a free [Alpaca](https://alpaca.markets) account (paper trading keys).

```bash
git clone https://github.com/Bhargavsinh-Solanki/global-political-trades-forecast.git
cd global-political-trades-forecast
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then paste your Alpaca paper keys into .env
```

Check everything works:

```bash
python step1_connect.py     # should print "Connected to Alpaca!"
pytest                      # runs the unit tests (no keys needed)
```

Open the dashboard:

```bash
streamlit run step11_dashboard.py
```
It opens at http://localhost:8501. Press Ctrl+C in the terminal to stop it.

### Daily routine (run by hand after the US market closes)
```bash
python step8_bot.py           # dry run: shows what the bot would do
python step8_bot.py --trade   # sends the paper orders
python step9_report.py        # report card for the paper account
```

## Project structure

```
├── helpers.py                # shared tools: Alpaca clients, data download, backtest maths
├── step1_connect.py … step13_live.py   # the lessons (see below)
├── step11_dashboard.py       # Streamlit dashboard (live section added in lesson 14)
├── tests/test_helpers.py     # unit tests on fake data
├── .github/workflows/        # CI: runs the tests on every push
├── docs/images/              # charts used in this README
├── data/                     # generated CSVs, charts, logs (not committed)
├── requirements.txt
└── .env.example              # template for your API keys
```

## Lessons

| # | File | What you learn |
|---|------|----------------|
| 1 | `step1_connect.py` | Logging in to Alpaca with API keys |
| 2 | `step2_prices.py` | Fetching the latest price and 30 days of daily prices |
| 3 | `step3_save_and_chart.py` | Saving a year of prices to CSV, moving average, drawing a chart |
| 4 | `step4_compare.py` | Lists, functions and loops; comparing returns and risk across stocks |
| 5 | `step5_backtest.py` | Backtesting a moving-average rule vs buy & hold; avoiding look-ahead bias |
| 6 | `step6_overfitting.py` | Trading costs, testing many settings, train/test split and overfitting |
| 7 | `step7_paper_order.py` | Placing paper orders (market vs limit), checking positions and orders |
| 8 | `step8_bot.py` | A dry-run-first trading bot: dictionaries, try/except, log files |
| 9 | `step9_report.py` | Daily report card: account value over time, positions, latest bot decisions |
| 10 | `step10_using_helpers.py` | Your own module (`helpers.py`) and automated tests (`tests/`) |
| 11 | `step11_dashboard.py` | A read-only web dashboard with Streamlit: widgets, caching, charts |
| 12 | `step12_news.py` | News headlines vs price moves: joining tables, grouping, correlation, news timing |
| 13 | `step13_live.py` | Live streaming trades and 1-minute bars over a websocket: callbacks, async, timers |
| 14 | `step11_dashboard.py` + repo | Live dashboard section (fragments, polling vs streaming); CI, licence, portfolio README |

## Built with

[alpaca-py](https://github.com/alpacahq/alpaca-py) ·
[pandas](https://pandas.pydata.org) ·
[matplotlib](https://matplotlib.org) ·
[Streamlit](https://streamlit.io) ·
[Altair](https://altair-viz.github.io) ·
[pytest](https://pytest.org) ·
GitHub Actions

---

## Glossary

**Data & APIs**
- **API**: a "menu" a company offers so programs can ask it for data.
- **API key**: your username and password for that menu. Keep it secret.
- **Bar / candle**: one time period summarised as Open, High, Low, Close, Volume.
- **CSV**: a plain-text spreadsheet; opens in Excel, Numbers or Google Sheets.
- **Request vs stream**: a request asks once and gets one answer (a letter); a stream stays open and data keeps arriving (a phone call).
- **Websocket**: the technology behind a stream - a connection that stays open both ways.
- **Polling**: asking "anything new?" again and again on a timer.
- **Unix timestamp**: a date stored as seconds since 1 January 1970.
- **SSL certificate**: a digital ID card that proves a website is who it says it is.

**Investing & trading**
- **Paper trading**: a practice account with fake money.
- **Return**: how much an investment grew or shrank, in %.
- **Volatility (typical daily move)**: how much a price usually jumps per day. Bigger = bumpier ride.
- **Biggest drop (max drawdown)**: the worst fall from a high point to a later low.
- **Benchmark (SPY)**: a fund tracking the 500 biggest US companies; the "average market" to compare against.
- **Moving average**: the average price over the last N days; smooths out noise to show the trend.
- **Compounding**: gains building on earlier gains, day after day.
- **Spread / slippage**: hidden trading costs - the gap between buy and sell prices, and price moving while your order fills.
- **Market order**: buy/sell now at the current price. Fast, but you don't pick the price.
- **Limit order**: buy/sell only at your price or better. You pick the price, but it may never fill.
- **Position**: a stock you currently own. **Filled**: the order actually happened.
- **Unrealized profit/loss**: how much a position is up or down on paper, before you sell.

**Testing strategies**
- **Backtest**: replaying a trading rule on old prices to see how it would have done.
- **Signal**: the rule's decision for each day (own the stock or hold cash).
- **Look-ahead bias**: accidentally using information you couldn't have had at the time. Makes results look too good.
- **Overfitting**: tuning a rule until it fits the past perfectly, including the luck, so it fails on new data.
- **Train / test split**: choose settings on old data, then judge them on newer data they've never seen.
- **Correlation**: a number from -1 to +1 showing how strongly two things move together.
- **Correlation is not causation**: two things moving together doesn't prove one causes the other.

**Coding**
- **Module**: a file of reusable tools that other files can `import`.
- **Test / assert**: a small program that checks other code gives a known right answer; `assert` means "this must be true".
- **CI (continuous integration)**: GitHub automatically runs the tests on every push.
- **Join / group by**: matching two tables on a shared column / sorting rows into buckets and counting them.
- **Callback**: a function you write but someone else (here, Alpaca's library) calls when something happens.
- **async / await**: Python's way to wait for many things at once without freezing.
- **Caching**: remembering a result for a while so you don't fetch it again on every click.
- **Fragment**: a part of a Streamlit page that can refresh on its own.
- **Bot / dry run / watchlist / log**: a program that trades by itself / a rehearsal that sends nothing / the stocks it may trade / its record of every decision.

## License

[MIT](LICENSE) © 2026 Bhargav Solanki
