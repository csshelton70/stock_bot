"""
App to scan alpaca for known stock symbols and make paper trades
"""

# standard
import time
from datetime import datetime
import configparser
import json

# third party
import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
import pytz

# Load API credentials from config file
config = configparser.ConfigParser()
config.read("config.ini")

API_KEY = config["alpaca"]["API_KEY"]
API_SECRET = config["alpaca"]["API_SECRET"]
POLL_INTERVAL = int(config["alpaca"]["POLL_INTERVAL"])
BASE_URL = "https://paper-api.alpaca.markets"
USE_TRADING_HOURS = config.getboolean("settings", "use_trading_hours")
if config.has_option("settings", "watch_list"):
    WATCH_LIST = config["settings"]["watch_list"].strip().upper().split(",")
else:
    WATCH_LIST = []  # Or any default value you'd like


TRADE_HISTORY_FILE = "trade_history.json"

# Define your local timezone (e.g., New York Time - Eastern Time)
LOCAL_TZ = pytz.timezone("America/New_York")  # Adjust to your local timezone

# Initialize Alpaca API
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")


def load_trade_history():
    """Load the trade history from file."""
    try:
        with open(TRADE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_trade_history(trade_history):
    """Save the trade history to file."""
    with open(TRADE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(trade_history, f, indent=4)


def fetch_data(ticker, timeframe="1Min", limit=100):
    """
    Fetch historical data for a given stock ticker.
    """
    try:
        # Fetch historical bars using `get_bars`
        bars = api.get_bars(symbol=ticker, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            {
                "timestamp": [b.t for b in bars],
                "open": [b.o for b in bars],
                "high": [b.h for b in bars],
                "low": [b.l for b in bars],
                "close": [b.c for b in bars],
                "volume": [b.v for b in bars],
            }
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None


def detect_bullish_engulfing(df):
    """Bullish Engulfing pattern"""
    return (
        (df["close"].shift(1) < df["open"].shift(1))
        & (df["open"] < df["close"])
        & (df["close"] > df["open"].shift(1))
    )


def detect_bearish_engulfing(df):
    """Bearish Engulfing pattern"""
    return (
        (df["close"].shift(1) > df["open"].shift(1))
        & (df["open"] > df["close"])
        & (df["open"] >= df["close"].shift(1))
        & (df["close"] <= df["open"].shift(1))
    )


def detect_hammer(df):
    """Hammer pattern"""
    body = abs(df["close"] - df["open"])
    lower_shadow = np.where(
        df["close"] > df["open"], df["open"] - df["low"], df["close"] - df["low"]
    )
    upper_shadow = np.where(
        df["close"] > df["open"], df["high"] - df["close"], df["high"] - df["open"]
    )

    return (lower_shadow > 2 * body) & (upper_shadow < 0.1 * body)


def detect_shooting_star(df):
    """Shooting Star pattern"""
    body = abs(df["close"] - df["open"])
    upper_shadow = np.where(
        df["close"] > df["open"], df["high"] - df["close"], df["high"] - df["open"]
    )
    lower_shadow = np.where(
        df["close"] > df["open"], df["low"] - df["open"], df["low"] - df["close"]
    )

    return (
        (upper_shadow > 2 * body)
        & (lower_shadow < 0.1 * body)
        & (df["close"] < df["open"])
    )


def detect_doji(df):
    """Doji pattern"""
    return abs(df["close"] - df["open"]) < 0.1 * (df["high"] - df["low"])


def detect_morning_star(df):
    """Morning Star pattern"""
    first = df["close"].shift(2) < df["open"].shift(2)
    second = detect_doji(df.shift(1))
    third = df["close"] > df["open"]

    return first & second & third


def detect_evening_star(df):
    """Evening Star pattern"""
    first = df["close"].shift(2) > df["open"].shift(2)
    second = detect_doji(df.shift(1))
    third = df["close"] < df["open"]

    return first & second & third


def analyze_candlesticks(df):
    """
    Analyze all candlestick patterns for sell/buy signals.
    """
    sell_signals = []
    buy_signals = []

    # Check for Bullish Patterns (Buy signals)
    if detect_bullish_engulfing(df).iloc[-1]:
        buy_signals.append("Bullish Engulfing")
    if detect_hammer(df).iloc[-1]:
        buy_signals.append("Hammer")
    if detect_morning_star(df).iloc[-1]:
        buy_signals.append("Morning Star")

    # Check for Bearish Patterns (Sell signals)
    if detect_bearish_engulfing(df).iloc[-1]:
        sell_signals.append("Bearish Engulfing")
    if detect_shooting_star(df).iloc[-1]:
        sell_signals.append("Shooting Star")
    if detect_evening_star(df).iloc[-1]:
        sell_signals.append("Evening Star")

    return buy_signals, sell_signals


def is_market_open():
    """
    Check if the current time is within market hours (9:30 AM to 4:00 PM).
    """
    now = datetime.now(LOCAL_TZ)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    # Return True if within market hours, else False
    return market_open <= now <= market_close


def get_active_stocks():
    """
    Fetch the list of active stocks (positions) in your Alpaca account.
    """
    try:
        positions = api.list_positions()
        active_stocks_list = [position.symbol for position in positions]
        return active_stocks_list
    except Exception as e:
        print(f"Error fetching active positions: {e}")
        return []


def place_buy_order(stock, amount=50):
    """Place a buy order for a stock"""
    try:
        # Fetch the latest price using get_bars (1 minute time frame for real-time data)
        bars = api.get_bars(stock, "minute", limit=1)
        last_price = bars[-1].c  # The close price of the last bar

        # Calculate the number of shares to buy based on the $50 buy amount
        qty = int(amount / last_price)

        # Place the buy order
        api.submit_order(
            symbol=stock, qty=qty, side="buy", type="market", time_in_force="gtc"
        )
        print(f"Buy order placed for {stock}!")
        return stock
    except Exception as e:
        print(f"Error placing buy order: {e}")
        return None


def place_sell_order(stock, qty):
    """Place a sell order for a stock"""
    try:
        api.submit_order(
            symbol=stock, qty=qty, side="sell", type="market", time_in_force="gtc"
        )
        print(f"Sell order placed for {stock}!")
        return stock
    except Exception as e:
        print(f"Error placing sell order: {e}")
        return None


def monitor_stocks(stocks_to_watch_list):
    """
    Monitor a list of stocks and notify when a sell signal is detected.
    """
    trade_history = load_trade_history()
    print(
        f"Monitoring the following stocks: {stocks_to_watch_list}."
    )

    while True:
        if (USE_TRADING_HOURS and is_market_open()) or ( not USE_TRADING_HOURS):

            for ticker in stocks_to_watch_list:
                if ticker in trade_history and trade_history[ticker]["date"] == str(
                    datetime.now().date()
                ):
                    print(f"Trade already performed for {ticker} today. Skipping.")
                    continue

                data = fetch_data(ticker)
                if data is not None and not data.empty:
                    buy_patterns, sell_patterns = analyze_candlesticks(data)
                    if sell_patterns:
                        print(
                            f"Sell signals detected for {ticker}: {sell_patterns}"
                        )
                        if ticker in trade_history:
                            qty = int(
                                api.get_account().cash
                                / api.get_last_trade(ticker).price
                            )
                            place_sell_order(ticker, qty)
                            trade_history[ticker] = {
                                "date": str(datetime.now().date()),
                                "action": "sell",
                            }
                            save_trade_history(trade_history)
                    elif buy_patterns:
                        print(f"Buy signals detected for {ticker}: {buy_patterns}")
                        place_buy_order(ticker)
                        trade_history[ticker] = {
                            "date": str(datetime.now().date()),
                            "action": "buy",
                        }
                        save_trade_history(trade_history)
                    else:
                        print(f"No signals for {ticker} at the moment.")
        else:
            print("Market is closed. Waiting for market hours...")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # Option 1: Use active stocks from Alpaca account
    active_stocks = get_active_stocks()
    all_stocks_to_watch = list(set(WATCH_LIST + active_stocks))

    # If no stocks to monitor, print an error
    if not all_stocks_to_watch:
        print("No stocks to monitor. Exiting script.")
    else:
        monitor_stocks(all_stocks_to_watch)
