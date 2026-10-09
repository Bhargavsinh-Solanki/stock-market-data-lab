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

## Glossary
- **API**: a "menu" a company offers so programs can ask it for data.
- **API key**: your username and password for that menu. Keep it secret.
- **Paper trading**: a practice account with fake money.
- **Bar / candle**: one time period summarised as Open, High, Low, Close, Volume.
- **CSV**: a plain-text spreadsheet; opens in Excel, Numbers or Google Sheets.
- **Moving average**: the average price over the last N days; smooths out noise to show the trend.
