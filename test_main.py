"""
Test cases for the main.py file.
"""

import json

from datetime import datetime, timedelta

# import time
from unittest.mock import patch, MagicMock, mock_open


# import pytest
import pandas as pd

import main


# --- 1. TESTING LOADING AND SAVING TRADE HISTORY ---
def test_load_trade_history_success():
    """_summary_"""
    # Mock file loading to return a pre-defined trade history
    trade_history_mock = {
        "AAPL": [
            {"action": "buy", "date": "2025-01-01", "price": 150.0, "quantity": 10}
        ]
    }

    with patch("builtins.open", mock_open(read_data=json.dumps(trade_history_mock))):
        result = main.load_trade_history()
        assert (
            result == trade_history_mock
        ), f"Expected {trade_history_mock}, but got {result}"


def test_load_trade_history_file_not_found():
    """
    _summary_
    """
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = main.load_trade_history()
        assert result == {}, "Expected empty dictionary on file not found"


def test_save_trade_history():
    """_summary_"""
    trade_history = {
        "AAPL": [
            {"action": "buy", "date": "2025-01-01", "price": 150.0, "quantity": 10}
        ]
    }

    with patch("builtins.open", mock_open()) as mock_file:
        main.save_trade_history(trade_history)
        mock_file.assert_called_once_with(
            main.TRADE_HISTORY_FILE, "w", encoding="utf-8"
        )
        mock_file().write.assert_called_once_with(json.dumps(trade_history, indent=4))


# --- 2. TESTING FETCHING DATA ---
@patch("main.api.get_bars")
def test_fetch_data_success(mock_get_bars):
    """_summary_

    Args:
        mock_get_bars (_type_): _description_
    """
    mock_get_bars.return_value = [
        MagicMock(t=datetime(2025, 1, 6, 10, 0), o=100, h=110, l=95, c=105, v=10000)
    ]

    ticker = "AAPL"
    result = main.fetch_data(ticker)

    assert result is not None
    assert len(result) == 1
    assert result["timestamp"][0] == pd.Timestamp("2025-01-06 10:00:00")
    assert result["close"][0] == 105


@patch("main.api.get_bars")
def test_fetch_data_failure(mock_get_bars):
    """_summary_

    Args:
        mock_get_bars (_type_): _description_
    """
    mock_get_bars.side_effect = Exception("API error")

    result = main.fetch_data("AAPL")
    assert result is None


# --- 3. TESTING CANDLESTICK PATTERNS ---
def test_detect_bullish_engulfing():
    """_summary_"""
    df = pd.DataFrame(
        {
            "open": [100, 90],
            "close": [110, 95],
        }
    )
    result = main.detect_bullish_engulfing(df)
    assert result.iloc[-1] == True


def test_detect_bearish_engulfing():
    """_summary_"""
    df = pd.DataFrame(
        {
            "open": [100, 110],
            "close": [90, 85],
        }
    )
    result = main.detect_bearish_engulfing(df)
    assert result.iloc[-1] == True


# --- 4. TESTING ORDER PLACING ---


# --- 5. TESTING TRADE HISTORY MANAGEMENT ---
def test_add_trade_to_history_new_trade():
    """_summary_"""
    trade_history = {}
    main.add_trade_to_history("AAPL", "buy", 150.0, 10)

    assert "AAPL" in trade_history
    assert len(trade_history["AAPL"]) == 1
    assert trade_history["AAPL"][0]["action"] == "buy"


def test_add_trade_to_history_existing_trade():
    """_summary_"""
    trade_history = {
        "AAPL": [
            {"action": "buy", "date": "2025-01-01", "price": 150.0, "quantity": 10}
        ]
    }

    main.add_trade_to_history("AAPL", "sell", 155.0, 5)

    assert len(trade_history["AAPL"]) == 2
    assert trade_history["AAPL"][1]["action"] == "sell"


# --- 6. TESTING MARKET OPEN STATUS ---
@patch("main.datetime")
def test_is_market_open(mock_datetime):
    """ """
    # Simulate market being open at 10:00 AM
    mock_datetime.now.return_value = datetime(2025, 1, 6, 10, 0, 0)
    result = main.is_market_open()
    assert result == True

    # Simulate market being closed at 7:00 PM
    mock_datetime.now.return_value = datetime(2025, 1, 6, 19, 0, 0)
    result = main.is_market_open()
    assert result == False


# --- 7. TESTING DATE-TIME CHECK FOR LAST TRADE ---


# --- 8. TESTING PDT (Pattern Day Trader) LIMIT ---
@patch("main.api.get_account")
def test_check_pdt_violation(mock_get_account):
    """_summary_

    Args:
        mock_get_account (_type_): _description_
    """
    mock_get_account.return_vaules = MagicMock(daytrade_count=0)

    #    result = main.check_pdt_violation()
    #    assert result == True

    mock_get_account.return_value = MagicMock(daytrade_count=5)
    result = main.check_pdt_violation()
    assert result
