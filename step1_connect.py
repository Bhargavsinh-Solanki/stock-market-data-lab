"""
STEP 1: Say hello to Alpaca.

Goal: prove that our program can log in to Alpaca using our keys.
We only READ information here. Nothing is bought or sold.

Run it with:   python step1_connect.py
"""

import os

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# 1) Load the secret keys from the .env file into memory.
load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")
use_paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"

if not api_key or "paste_your" in api_key:
    raise SystemExit("No keys found. Open the .env file and paste your Alpaca keys first.")

# 2) Create a "client" - think of it as a phone line to Alpaca.
client = TradingClient(api_key, secret_key, paper=use_paper)

# 3) Ask Alpaca: "Tell me about my account."
account = client.get_account()

print("Connected to Alpaca!")
print("Account type :", "PAPER (practice money)" if use_paper else "LIVE (real money)")
print("Status       :", account.status)
print("Cash         : $", account.cash)
print("Buying power : $", account.buying_power)
