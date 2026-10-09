# Stock Data Project (Student Learning Project)

A personal project to learn coding by working with real stock market data from **Alpaca**.
This is for learning only and is not financial advice.

## Setup (one time)

```bash
python3 -m venv .venv              # create a private toolbox for this project
source .venv/bin/activate          # step into the toolbox (do this every new terminal)
pip install -r requirements.txt    # install the tools listed in requirements.txt
cp .env.example .env               # then paste your Alpaca keys into .env
```

## Lessons

| Step | File | What you learn |
|------|------|----------------|
| 1 | `step1_connect.py` | Logging in to Alpaca with API keys |
| 2 | `step2_prices.py`  | Fetching the latest price and 30 days of daily prices |
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

### Opening the dashboard
```bash
streamlit run step11_dashboard.py
```
It opens at http://localhost:8501. Press Ctrl+C in the terminal to stop it.

### Running the tests
```bash
pytest
```

### Daily routine (run by hand after the US market closes)
```bash
source .venv/bin/activate
python step8_bot.py --trade
python step9_report.py
```

## Glossary
- **API**: a "menu" a company offers so programs can ask it for data.
- **API key**: your username and password for that menu. Keep it secret.
- **Paper trading**: a practice account with fake money.
- **Bar / candle**: one time period summarised as Open, High, Low, Close, Volume.
- **CSV**: a plain-text spreadsheet; opens in Excel, Numbers or Google Sheets.
- **Moving average**: the average price over the last N days; smooths out noise to show the trend.
- **Return**: how much an investment grew or shrank, in %.
- **Volatility (typical daily move)**: how much a price usually jumps per day. Bigger = bumpier ride.
- **Biggest drop (max drawdown)**: the worst fall from a high point to a later low.
- **Benchmark (SPY)**: a fund tracking the 500 biggest US companies; the "average market" to compare against.
- **Backtest**: replaying a trading rule on old prices to see how it would have done.
- **Signal**: the rule's decision for each day (own the stock or hold cash).
- **Look-ahead bias**: accidentally using information you couldn't have had at the time. Makes results look too good.
- **Compounding**: gains building on earlier gains, day after day.
- **Spread / slippage**: hidden trading costs - the gap between buy and sell prices, and price moving while your order fills.
- **Overfitting**: tuning a rule until it fits the past perfectly, including the luck, so it fails on new data.
- **Train / test split**: choose settings on old data, then judge them on newer data they've never seen.
- **Market order**: buy/sell now at the current price. Fast, but you don't pick the price.
- **Limit order**: buy/sell only at your price or better. You pick the price, but it may never fill.
- **Position**: a stock you currently own.
- **Filled**: the order actually happened.
- **Bot**: a program that makes and carries out trading decisions by itself.
- **Dry run**: a rehearsal - the bot shows what it would do but sends nothing.
- **Watchlist**: the list of stocks the bot is allowed to trade.
- **Log**: a file recording every decision, so you can look back later.
- **Unix timestamp**: a date stored as seconds since 1 January 1970 - how computers often store time.
- **Unrealized profit/loss**: how much a position is up or down on paper, before you sell.
- **Module**: a file of reusable tools that other files can `import`.
- **Test**: a small program that checks other code gives the answer you already know is right.
- **Assert**: "this must be true" - if it isn't, the test fails.
- **Dashboard**: a page that shows your key numbers and charts at a glance.
- **Widget**: an interactive control on a page - slider, text box, button, dropdown.
- **Caching**: remembering a result for a while so you don't fetch it again on every click.
- **localhost**: your own computer acting as a website, visible only to you.
- **Join**: matching two tables row by row using a shared column, such as the date.
- **Group by**: sorting rows into buckets (e.g. by day) and counting or averaging each bucket.
- **Correlation**: a number from -1 to +1 showing how strongly two things move together.
- **Correlation is not causation**: two things moving together doesn't prove one causes the other.
