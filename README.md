# Stock Market Data Lab

[![tests](https://github.com/Bhargavsinh-Solanki/stock-market-data-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/Bhargavsinh-Solanki/stock-market-data-lab/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.14-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A hands-on learning project that uses the **[Alpaca](https://alpaca.markets) API** to fetch
live and historical stock market data, test trading rules honestly, run a paper-trading bot,
and show it all on a live web dashboard.

It's built as **18 small, heavily commented lessons**, each one adding a new coding idea.

> ⚠️ Educational project only. Paper trading (fake money). Not financial advice.

---

## What it does

| Area | Highlights |
|---|---|
| **Market data** | Historical daily and 1-minute bars, latest trades, news headlines, live websocket stream |
| **Web crawling** | Own polite crawler: Alpaca + Yahoo Finance RSS into a growing news archive, robots.txt-aware article text extraction |
| **Analysis** | Returns, volatility, max drawdown, moving averages, news volume and headline sentiment (word list and FinBERT AI) vs price moves |
| **Backtesting & statistics** | Moving-average strategy vs buy & hold, trading costs, train/test split, shuffle (permutation) tests across 12 stocks |
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
3. **Busy news days really are bigger move days.** On the busiest 20% of news days, AAPL and TSLA moved
   about 1.5× as much as on a typical day. A shuffle test confirmed this for **8 of 12 stocks** (p < 0.05), so it's
   a repeatable effect, though it doesn't show whether news causes moves or moves cause news.
4. **"Good news today → price up tomorrow" is luck.** Apple looked convincing (+0.64% next day,
   p = 0.013), but across 12 stocks only **1 of 12** passed, about what pure chance produces
   (12 × 5% ≈ 0.6). A classic case of the multiple-testing trap.
5. **A real AI model didn't change that.** FinBERT, run locally, read headlines far better than the
   word list (it wasn't fooled by "…Earnings Beat" in a negative story), yet its "good news" days
   predicted the next day for **0 of 12** stocks. Better reading ≠ a trading edge.

<table>
<tr>
<td><img src="docs/images/backtest.png" alt="SPY backtest: moving-average rule vs buy and hold"></td>
<td><img src="docs/images/overfitting.png" alt="TSLA: best setting on training data fails on test data"></td>
</tr>
<tr>
<td><img src="docs/images/compare.png" alt="Growth of $100 in AAPL, MSFT, TSLA and SPY"></td>
<td><img src="docs/images/news.png" alt="AAPL news stories per day vs daily price move"></td>
</tr>
<tr>
<td colspan="2"><img src="docs/images/luck_test.png" alt="Shuffle tests: real results vs 10,000 random picks of days"></td>
</tr>
</table>

## Things I was careful about

- **No look-ahead bias.** Signals act the *next* day (`shift(1)`), and news published after the
  16:00 New York close is matched to the next trading day. Both are covered by unit tests.
- **Trading costs** are included in backtests (0.1% per switch).
- **Out-of-sample testing.** Strategy settings are chosen on old data and judged on newer data.
- **Luck checks.** Patterns are shuffle-tested against 10,000 random picks, then re-checked on 12 stocks.
- **Polite crawling.** The crawler obeys robots.txt, waits between visits, identifies itself, never
  re-downloads a page, and skips sites whose terms forbid scraping.
- **Safety.** All trading code is locked to the paper account. The bot dry-runs by default and only
  touches symbols on its watchlist. API keys stay in `.env`, which is never committed.

---

## Getting started

You need Python 3.12+ and a free [Alpaca](https://alpaca.markets) account (paper trading keys).

```bash
git clone https://github.com/Bhargavsinh-Solanki/stock-market-data-lab.git
cd stock-market-data-lab
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

### Run the crawler automatically (optional)
macOS has a built-in scheduler called **cron**. To grow the news archive every 2 hours on weekdays,
run `crontab -e`, paste this one line (change the folder path if yours differs), save and close:
```
0 */2 * * 1-5 cd ~/Github/global-political-trades-forecast && .venv/bin/python step17_news_crawler.py >> data/crawler.log 2>&1
```
Check it's there with `crontab -l`. Remove it again with `crontab -e` (delete the line).
Cron skips runs while the Mac is asleep or off, which is fine: the next run catches up on new headlines.

## Project structure

```
├── helpers.py                # shared tools: Alpaca clients, data download, backtest maths
├── crawler.py                # polite news crawler: RSS, archive, robots.txt, article text
├── ai_sentiment.py           # FinBERT sentiment, run locally, with a score cache
├── step1_connect.py … step18_ai_sentiment.py   # the lessons (see below)
├── step11_dashboard.py       # Streamlit dashboard (live section added in lesson 14)
├── tests/                    # unit tests on fake data (no internet or keys needed)
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
| 15 | `step15_sentiment.py` | Scoring headlines as good/bad news: sets, regex, `.apply()`, same-day vs next-day tests |
| 16 | `step16_luck_test.py` | Real or luck? Shuffle tests, p-values, multiple testing: numpy, random seeds, simulation |
| 17 | `step17_news_crawler.py` | Your own polite web crawler and a growing news archive: classes, XML/RSS, HTTP, de-duplication |
| 18 | `step18_ai_sentiment.py` | A free AI (FinBERT) reads the news on your Mac: pre-trained models, probabilities, mocks, caching |

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
- **RSS feed**: a list of a site's newest stories, written in XML, meant to be read by programs.
- **Crawler (scraper)**: a program that visits web pages and saves information from them.
- **robots.txt**: a website's rules for robots: which pages crawlers may and may not visit.
- **User-Agent**: the name badge a program shows a website when it visits.
- **HTTP status code**: a website's reply code: 200 = OK, 403 = forbidden, 404 = not found.

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
- **Sentiment**: whether a piece of text sounds positive or negative.
- **Noise**: random ups and downs that can look like a pattern, especially in small samples.
- **Shuffle test (permutation test)**: compare your result with thousands of random picks to see if luck could explain it.
- **p-value**: the share of random picks that did at least as well as yours. Under 0.05 = "unlikely to be luck".
- **Multiple testing**: try enough ideas and some will pass by chance (about 1 in 20 at p < 0.05).

**Coding**
- **Module**: a file of reusable tools that other files can `import`.
- **Test / assert**: a small program that checks other code gives a known right answer; `assert` means "this must be true".
- **CI (continuous integration)**: GitHub automatically runs the tests on every push.
- **Join / group by**: matching two tables on a shared column / sorting rows into buckets and counting them.
- **Callback**: a function you write but someone else (here, Alpaca's library) calls when something happens.
- **async / await**: Python's way to wait for many things at once without freezing.
- **Caching**: remembering a result for a while so you don't fetch it again on every click.
- **Fragment**: a part of a Streamlit page that can refresh on its own.
- **Set**: a collection of unique items with very fast "is this in it?" checks.
- **NumPy**: a library for fast maths on whole lists of numbers at once.
- **Random seed**: a starting number that makes "random" results repeatable.
- **Histogram**: a bar chart of how often each value came up.
- **Class**: a bundle of data and the functions that work on it (e.g. `PoliteFetcher`).
- **Hash**: a short fingerprint of some text; the same text always gives the same hash.
- **De-duplication**: making sure the same item is never stored twice.
- **Pre-trained model**: an AI someone else already trained; you just use it ("inference").
- **Probability**: how sure the model is, from 0% to 100% (e.g. "92% positive").
- **Mock**: a fake stand-in used in tests (here, a fake FinBERT) so tests are fast and predictable.
- **Lazy loading**: only loading something heavy at the moment it's first needed.
- **cron**: the Mac/Linux built-in scheduler that runs commands at set times.
- **Regular expression (regex)**: a pattern for finding text, e.g. `[a-z]+` means "a run of letters".
- **Bot / dry run / watchlist / log**: a program that trades by itself / a rehearsal that sends nothing / the stocks it may trade / its record of every decision.

## License

[MIT](LICENSE) © 2026 Bhargav Solanki
