"""
App to scan alpaca for known stock symbols and make paper trades
"""

# standard
import time
from datetime import datetime, timedelta
import configparser
import json
import math
import requests

# from collections import defaultdict


# third party
import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
import pytz

CONFIG_FILE = "config.ini"
TRADE_HISTORY_FILE = "trade_history.json"

# Load API credentials from config file
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

API_KEY = config["alpaca"]["API_KEY"]
API_SECRET = config["alpaca"]["API_SECRET"]
POLL_INTERVAL = config.get("alpaca", "POLL_INTERVAL", fallback="15Min")
BASE_URL = "https://paper-api.alpaca.markets"
USE_TRADING_HOURS = config.getboolean("settings", "use_trading_hours")
if config.has_option("settings", "watch_list"):
    WATCH_LIST = config["settings"]["watch_list"].strip().upper().split(",")
else:
    WATCH_LIST = []  # Or any default value you'd like
MAX_SPEND_PER_TRADE = config.get("settings", "max_spend_per_trade", fallback=50)
tradeable_info = {}

# Define your local timezone (e.g., New York Time - Eastern Time)
LOCAL_TZ = pytz.timezone("America/New_York")  # Adjust to your local timezone

# Initialize Alpaca API
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")


def check_pdt_violation() -> bool:
    """
    Check if the next trade will exceed the PDT limit.

    Args:
        api_key (str): Alpaca API key.
        api_secret (str): Alpaca API secret.

    Returns:
        bool: True if the next trade will violate PDT rules, False otherwise.
    """
    base_url = "https://paper-api.alpaca.markets/v2"  # Use live URL for production
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET,
    }
    account_url = f"{base_url}/account"

    # Fetch account details
    response = requests.get(account_url, headers=headers)
    if response.status_code != 200:
        print(f"Error: {response.status_code}, {response.text}")
        return False

    account_data = response.json()
    daytrade_count = account_data.get("daytrade_count", 0)
    pattern_day_trader = account_data.get("pattern_day_trader", False)

    # PDT violation logic
    if pattern_day_trader:
        print("Warning: You are already flagged as a Pattern Day Trader.")
        return True
    elif daytrade_count >= 3:
        print("Warning: Executing another day trade will exceed the PDT limit.")
        return True

    return False


def add_trade_to_history(ticker: str, action: str, price: float, quantity: int) -> None:
    """
    Adds a new trade entry to the trade history for a given stock ticker.

    This function updates the trade history by appending a new trade entry
    with the specified action (buy/sell), price, and quantity. If the ticker
    already exists in the trade history, the new trade is added to the list
    of trades for that ticker. If the ticker does not exist, a new entry
    is created. The updated trade history is then saved to a JSON file.

    Args:
        ticker (str): The stock symbol (e.g., 'AAPL', 'GOOG') for which the trade is being made.
        action (str): The action of the trade ('buy' or 'sell').
        price (float): The price at which the trade was executed.
        quantity (int): The number of shares involved in the trade.

    Returns:
        None: This function does not return a value. It modifies the trade history file.

    Example:
        add_trade_to_history('AAPL', 'buy', 150.25, 10)
        add_trade_to_history('GOOG', 'sell', 2800.00, 5)
    """
    trade_history = load_trade_history()

    # Create a new trade entry
    new_trade = {
        "action": action,
        "date": str(datetime.now().date()),
        "price": price,
        "quantity": quantity,
    }

    # If the ticker already exists in the trade history, append the new trade to the list
    if ticker in trade_history:
        trade_history[ticker].append(new_trade)
    else:
        trade_history[ticker] = [new_trade]

    # Save the updated trade history back to the file
    save_trade_history(trade_history)
    trade_history = load_trade_history()


def load_trade_history():
    """
    Loads the trade history from the trade history JSON file.

    This function attempts to read the trade history from a JSON file. If the 
    file is found, it parses the contents and returns the trade history as 
    a dictionary. If the file does not exist, an empty dictionary is returned.

    Returns:
        dict: A dictionary representing the trade history. The keys are stock
              tickers, and the values are lists of trade entries.

    Example:
        trade_history = load_trade_history()
    """
    try:
        with open(TRADE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_trade_history(trade_history: str) -> None:
    """
    Saves the provided trade history to a JSON file.

    This function serializes the trade history string and writes it to a
    JSON file. The content is formatted with indentation for better
    readability. If the file does not exist, it will be created.

    Args:
        trade_history (str): A JSON-formatted string representing the trade 
                              history data.

    Example:
        trade_history = '{"AAPL": [{"action": "buy", "date": "2025-01-01", "price": 150, "quantity": 10}]}'
        save_trade_history(trade_history)
    """
    with open(TRADE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(trade_history, f, indent=4)


def get_current_price(ticker: str) -> float:
    """
    Fetches the current price of a given stock ticker.

    This function retrieves the most recent 1-minute bar data for the
    specified ticker and returns the closing price of the last bar.

    Args:
        ticker (str): The stock ticker symbol for which the current price
                      is to be fetched.

    Returns:
        float: The closing price of the most recent 1-minute bar for the
               given stock ticker.

    Raises:
        Exception: If there is an error retrieving the data or the data 
                   is not available.

    Example:
        current_price = get_current_price("AAPL")
    """
    bars = api.get_bars(symbol=ticker, timeframe="1min", limit=1)

    return bars[-1].c


def is_last_trade_older_than_15_minutes(ticker:str, trade_history:dict) -> bool:
    """
    Check if the last trade for a given ticker is more than 15 minutes old.

    Args:
        ticker (str): The stock ticker symbol.
        trade_history (dict): The trade history dictionary with trade details.

    Returns:
        bool: True if the last trade is older than 15 minutes, False otherwise.
    """
    last_trade = get_last_trade(ticker, trade_history)

    if last_trade:
        last_trade_time = datetime.strptime(last_trade["date"], "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_trade_time

        if time_diff < timedelta(minutes=15):
            print(
                f"Trade for {ticker} is being skipped. Last trade was {time_diff} ago."
            )
            return False

    return True


def fetch_data(ticker, timeframe=POLL_INTERVAL, limit=100):
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


def get_last_trade(ticker, trade_history):
    """Get the last trade for the given ticker."""
    if ticker in trade_history:
        # Get the last trade (most recent entry in the list)
        return trade_history[ticker][-1]  # Returns the most recent trade for the ticker
    return None


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


def analyze_stock_for_trading(ticker):
    """Analyze the stock for buy/sell signals."""
    data = fetch_data(ticker)
    if data is not None and not data.empty:
        buy_patterns, sell_patterns = analyze_candlesticks(data)
        return buy_patterns, sell_patterns
    return [], []


def perform_buy_order_if_needed(ticker, buy_patterns, trade_history):
    """Perform buy order if conditions are met."""
    if buy_patterns:
        if tradeable_info.get(ticker) is True or is_market_open():
            if check_pdt_violation():
                return

            if not is_last_trade_older_than_15_minutes(ticker, trade_history):
                return

            print(f"Buy signals detected for {ticker}: {buy_patterns}")
            bars = api.get_bars(ticker, "minute", limit=1)
            last_price = bars[-1].c  # The close price of the last bar

            # Calculate the number of shares to buy based on the $50 buy amount
            qty = float(20 / last_price)

            # Place the buy order
            api.submit_order(
                symbol=ticker, qty=qty, side="buy", type="market", time_in_force="day"
            )

            add_trade_to_history(ticker, "buy", last_price, qty)


def perform_sell_order_if_needed(ticker, sell_patterns, trade_history):
    """Perform sell order if conditions are met."""
    positions = api.list_positions()
    current_position = next((p for p in positions if p.symbol == ticker), None)

    if sell_patterns and current_position is not None:
        if tradeable_info.get(ticker) is True or is_market_open():
            if check_pdt_violation():
                return

            if not is_last_trade_older_than_15_minutes(ticker, trade_history):
                return

            print(f"Sell signals detected for {ticker}: {sell_patterns}")

            try:
                # Calculate 20% of the owned quantity, rounded up
                qty = math.ceil(int(current_position.qty) * 0.20)
                price = get_current_price(
                    ticker
                )  # Assuming this function gets the current price
                api.submit_order(
                    symbol=ticker,
                    qty=qty,
                    side="sell",
                    type="market",
                    time_in_force="day",
                    extended_hours=True,
                )
                print(f"Sell order placed for {ticker}!")

                add_trade_to_history(ticker, "sell", price, qty)
            except Exception as e:
                print(f"Error placing sell order: {e}")
                return None
        else:
            print(f"{ticker} is not tradable after hours. Skipping sell order.")
    else:
        print(f"{ticker} is not owned, cannot sell.")


def monitor_stocks(stocks_to_watch_list):
    """
    Monitor a list of stocks and notify when a sell signal is detected.
    """
    trade_history = load_trade_history()
    print(f"Monitoring the following stocks: {stocks_to_watch_list}.")

    while True:
        for ticker in stocks_to_watch_list:
            buy_patterns, sell_patterns = analyze_stock_for_trading(ticker)
            if (not buy_patterns) and (not sell_patterns):
                print(f"No buy or sell signals detected for {ticker}.")
                continue
            perform_sell_order_if_needed(ticker, sell_patterns, trade_history)
            perform_buy_order_if_needed(ticker, buy_patterns, trade_history)

        time.sleep(60)


def load_stock_list():
    """Load the list of active stocks and combine with WATCH_LIST."""
    active_stocks = get_active_stocks()

    # Remove any active stocks that are already in WATCH_LIST
    combined_stocks = list(set(WATCH_LIST + active_stocks))

    # Update the WATCH_LIST in config.ini
    config.set("settings", "watch_list", ",".join(combined_stocks))
    with open("config.ini", "w", encoding="utf-8") as configfile:
        config.write(configfile)

    config.read("config.ini")

    return combined_stocks


def check_after_hours_tradability(stock_list) -> dict:
    """
    Check if stocks can be traded after hours.

    Args:
        stock_list (list): List of stock symbols to check.

    Returns:
        dict: Dictionary with stock symbols as keys and their after-hours tradability status as values.
    """
    tradability_status = {}

    for stock in stock_list:
        try:
            # Fetch asset details using the Alpaca API
            asset = api.get_asset(stock)
            # Check if the asset is tradable and eligible for extended hours
            if asset.tradable and asset.marginable:
                tradability_status[stock] = True
            else:
                tradability_status[stock] = False
        except Exception as e:
            print(f"Error checking tradability for {stock}: {e}")
            tradability_status[stock] = "Error"

    return tradability_status


if __name__ == "__main__":

    all_stocks_to_watch = load_stock_list()
    tradable_info = check_after_hours_tradability(all_stocks_to_watch)

    if not all_stocks_to_watch:
        print("No stocks to monitor. Exiting script.")
    else:
        monitor_stocks(all_stocks_to_watch)
