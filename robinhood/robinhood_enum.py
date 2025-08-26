"""
Robinhood Crypto API Enumerations Module
========================================

This module defines all enumeration classes used throughout the Robinhood Crypto API client.
These enums provide type safety and ensure only valid values are used for API parameters.

Classes:
    OrderSide: Buy or sell order sides
    OrderType: Types of orders (market, limit, stop, etc.)
    OrderState: Order execution states
    TimeInForce: Order time validity options
    EstimatedPriceSide: Price quote sides

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

from enum import Enum


class OrderSide(Enum):
    """
    Order side enumeration for buy/sell operations.

    This enum defines the valid sides for placing orders on the Robinhood platform.

    Attributes:
        BUY: Buy order - purchasing cryptocurrency
        SELL: Sell order - selling cryptocurrency
    """

    BUY = "buy"
    SELL = "sell"

    def __str__(self) -> str:
        """Return the string representation of the order side."""
        return self.value


class OrderType(Enum):
    """
    Order type enumeration for different execution strategies.

    This enum defines the types of orders that can be placed through the API.

    Attributes:
        MARKET: Market order - executes immediately at current market price
        LIMIT: Limit order - executes only at specified price or better
        STOP_LOSS: Stop loss order - sells when price drops to stop price
        STOP_LIMIT: Stop limit order - places limit order when stop price is reached
    """

    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"

    def __str__(self) -> str:
        """Return the string representation of the order type."""
        return self.value


class OrderState(Enum):
    """
    Order state enumeration for tracking order execution status.

    This enum defines the possible states an order can be in during its lifecycle.

    Attributes:
        OPEN: Order is active and waiting to be filled
        CANCELED: Order has been cancelled by user or system
        PARTIALLY_FILLED: Order has been partially executed
        FILLED: Order has been completely executed
        FAILED: Order failed to execute due to an error
    """

    OPEN = "open"
    CANCELED = "canceled"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    FAILED = "failed"

    def __str__(self) -> str:
        """Return the string representation of the order state."""
        return self.value

    @property
    def is_terminal(self) -> bool:
        """
        Check if the order state is terminal (no further changes expected).

        Returns:
            bool: True if the order state is terminal
        """
        return self in {self.CANCELED, self.FILLED, self.FAILED}

    @property
    def is_active(self) -> bool:
        """
        Check if the order is in an active state.

        Returns:
            bool: True if the order is active (open or partially filled)
        """
        return self in {self.OPEN, self.PARTIALLY_FILLED}


class TimeInForce(Enum):
    """
    Time in force enumeration for order validity periods.

    This enum defines how long an order remains active in the market.

    Attributes:
        GTC: Good Till Canceled - order remains active until filled or cancelled
        IOC: Immediate or Cancel - execute immediately or cancel unfilled portion
        FOK: Fill or Kill - execute completely immediately or cancel entire order
    """

    GTC = "gtc"  # Good Till Canceled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill

    def __str__(self) -> str:
        """Return the string representation of the time in force."""
        return self.value

    @property
    def description(self) -> str:
        """
        Get a human-readable description of the time in force.

        Returns:
            str: Description of the time in force behavior
        """
        descriptions = {
            self.GTC: "Good Till Canceled - remains active until filled or cancelled",
            self.IOC: "Immediate or Cancel - execute immediately or cancel unfilled",
            self.FOK: "Fill or Kill - execute completely immediately or cancel entirely",
        }
        return descriptions[self]


class EstimatedPriceSide(Enum):
    """
    Estimated price side enumeration for market data requests.

    This enum defines which side of the order book to get price estimates for.

    Attributes:
        BID: Bid side - price for selling (what buyers are willing to pay)
        ASK: Ask side - price for buying (what sellers are asking)
        BOTH: Both sides - get both bid and ask prices
    """

    BID = "bid"
    ASK = "ask"
    BOTH = "both"

    def __str__(self) -> str:
        """Return the string representation of the price side."""
        return self.value

    @property
    def is_for_buying(self) -> bool:
        """
        Check if this price side is used for buying operations.

        Returns:
            bool: True if this side is used when buying (ASK side)
        """
        return self == self.ASK

    @property
    def is_for_selling(self) -> bool:
        """
        Check if this price side is used for selling operations.

        Returns:
            bool: True if this side is used when selling (BID side)
        """
        return self == self.BID


# Utility functions for enums
def get_order_side_from_string(side_str: str) -> OrderSide:
    """
    Convert a string to OrderSide enum.

    Args:
        side_str: String representation of order side

    Returns:
        OrderSide: Corresponding enum value

    Raises:
        ValueError: If the string doesn't match any valid order side
    """
    try:
        return OrderSide(side_str.lower())
    except ValueError as exc:
        valid_sides = [side.value for side in OrderSide]
        raise ValueError(
            f"Invalid order side '{side_str}'. Valid options: {valid_sides}"
        ) from exc


def get_order_type_from_string(type_str: str) -> OrderType:
    """
    Convert a string to OrderType enum.

    Args:
        type_str: String representation of order type

    Returns:
        OrderType: Corresponding enum value

    Raises:
        ValueError: If the string doesn't match any valid order type
    """
    try:
        return OrderType(type_str.lower())
    except ValueError as exc:
        valid_types = [otype.value for otype in OrderType]
        raise ValueError(
            f"Invalid order type '{type_str}'. Valid options: {valid_types}"
        ) from exc
