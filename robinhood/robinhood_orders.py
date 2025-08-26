"""
Robinhood Crypto API Order Management Module
============================================

This module provides order management functionality for the Robinhood Crypto API.
It includes methods for retrieving, placing, and canceling cryptocurrency orders.

Classes:
    OrdersClient: Client for order management operations

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

import uuid
from typing import Any, Dict, List, Optional

from .robinhood_base import RobinhoodBaseClient
from .robinhood_enum import OrderSide, OrderState, OrderType, TimeInForce
from .robinhood_error import RobinhoodValidationError

# pylint:disable=broad-exception-caught


class OrdersClient(RobinhoodBaseClient):
    """
    Client for Robinhood Crypto order management operations.

    This class provides methods for retrieving order history, placing new orders,
    canceling existing orders, and managing all aspects of cryptocurrency trading.
    """

    def get_orders(
        self,
        symbol: Optional[str] = None,
        side: Optional[OrderSide] = None,
        state: Optional[OrderState] = None,
        order_type: Optional[OrderType] = None,
        created_at_start: Optional[str] = None,
        created_at_end: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get orders with optional filtering.

        Retrieves order history with various filtering options to find specific
        orders based on symbol, side, state, type, and time ranges.

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")
            side: Order side (buy/sell)
            state: Order state (open, filled, canceled, etc.)
            order_type: Order type (market, limit, stop_loss, stop_limit)
            created_at_start: Start time filter (ISO 8601 format)
            created_at_end: End time filter (ISO 8601 format)
            limit: Number of results per page
            cursor: Pagination cursor

        Returns:
            Dict[str, Any]: Orders information containing:
                - results: List of order objects
                - next: URL for next page
                - previous: URL for previous page

        Raises:
            RobinhoodAPIError: If the request fails

        Example:
            >>> from robinhood_enum import OrderSide, OrderState
            >>> client = OrdersClient()
            >>> orders = client.get_orders(
            ...     symbol="BTC-USD",
            ...     side=OrderSide.BUY,
            ...     state=OrderState.FILLED,
            ...     limit=10
            ... )
            >>> for order in orders['results']:
            ...     print(f"Order {order['id']}: {order['side']} {order['symbol']}")
        """
        params = []
        if symbol:
            params.append(f"symbol={symbol.upper()}")
        if side:
            params.append(f"side={side.value}")
        if state:
            params.append(f"state={state.value}")
        if order_type:
            params.append(f"type={order_type.value}")
        if created_at_start:
            params.append(f"created_at_start={created_at_start}")
        if created_at_end:
            params.append(f"created_at_end={created_at_end}")
        if limit:
            params.append(f"limit={limit}")
        if cursor:
            params.append(f"cursor={cursor}")

        query_params = "?" + "&".join(params) if params else ""
        path = f"/api/v1/crypto/trading/orders/{query_params}"
        return self.make_request("GET", path)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get specific order by ID.

        Retrieves detailed information about a specific order including
        execution details, current status, and order configuration.

        Args:
            order_id: Order ID to retrieve

        Returns:
            Dict[str, Any]: Detailed order information

        Raises:
            RobinhoodAPIError: If the request fails or order not found

        Example:
            >>> client = OrdersClient()
            >>> order = client.get_order("order-id-here")
            >>> print(f"Order Status: {order['state']}")
            >>> print(f"Filled Quantity: {order['filled_asset_quantity']}")
        """
        if not order_id:
            raise RobinhoodValidationError("Order ID is required")

        path = f"/api/v1/crypto/trading/orders/{order_id}/"
        return self.make_request("GET", path)

    def get_all_orders_paginated(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Get all orders using pagination to retrieve complete order history.

        Args:
            **kwargs: Same arguments as get_orders() method

        Returns:
            List[Dict[str, Any]]: All orders across all pages

        Raises:
            RobinhoodAPIError: If any request fails

        Example:
            >>> client = OrdersClient()
            >>> all_orders = client.get_all_orders_paginated(symbol="BTC-USD")
            >>> print(f"Total BTC orders: {len(all_orders)}")
        """
        all_orders = []
        cursor = None

        while True:
            response = self.get_orders(cursor=cursor, **kwargs)
            all_orders.extend(response.get("results", []))

            next_url = response.get("next")
            if not next_url:
                break

            # Extract cursor from next URL
            if "cursor=" in next_url:
                cursor = next_url.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_orders

    def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        asset_quantity: Optional[float] = None,
        quote_amount: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place a market order for immediate execution.

        Market orders execute immediately at the current market price.
        You can specify either the asset quantity or the quote amount (USD).

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")
            side: Order side (buy/sell)
            asset_quantity: Amount of cryptocurrency to trade
            quote_amount: USD amount to trade (alternative to asset_quantity)
            client_order_id: Optional client-provided order ID for tracking

        Returns:
            Dict[str, Any]: Order response with order details

        Raises:
            RobinhoodValidationError: If neither or both quantities are provided
            RobinhoodAPIError: If the request fails

        Example:
            >>> from robinhood_enum import OrderSide
            >>> client = OrdersClient()
            >>>
            >>> # Buy $100 worth of Bitcoin
            >>> order = client.place_market_order(
            ...     symbol="BTC-USD",
            ...     side=OrderSide.BUY,
            ...     quote_amount=100.0
            ... )
            >>> print(f"Order placed: {order['id']}")
            >>>
            >>> # Sell 0.001 Bitcoin
            >>> order = client.place_market_order(
            ...     symbol="BTC-USD",
            ...     side=OrderSide.SELL,
            ...     asset_quantity=0.001
            ... )
        """
        if not asset_quantity and not quote_amount:
            raise RobinhoodValidationError(
                "Either asset_quantity or quote_amount must be provided"
            )
        if asset_quantity and quote_amount:
            raise RobinhoodValidationError(
                "Only one of asset_quantity or quote_amount can be provided"
            )

        market_config = {}
        if asset_quantity:
            market_config["asset_quantity"] = str(asset_quantity)
        if quote_amount:
            market_config["quote_amount"] = str(quote_amount)

        body = {
            "client_order_id": client_order_id or str(uuid.uuid4()),
            "side": side.value,
            "type": OrderType.MARKET.value,
            "symbol": symbol.upper(),
            "market_order_config": market_config,
        }

        return self.make_request("POST", "/api/v1/crypto/trading/orders/", body)

    def place_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        limit_price: float,
        asset_quantity: Optional[float] = None,
        quote_amount: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place a limit order that executes only at a specific price or better.

        Limit orders will only execute at the specified price or better,
        providing price control but no guarantee of execution.

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")
            side: Order side (buy/sell)
            limit_price: Maximum price for buy orders, minimum price for sell orders
            asset_quantity: Amount of cryptocurrency to trade
            quote_amount: USD amount to trade (alternative to asset_quantity)
            time_in_force: How long the order remains active (default: GTC)
            client_order_id: Optional client-provided order ID

        Returns:
            Dict[str, Any]: Order response with order details

        Raises:
            RobinhoodValidationError: If neither or both quantities are provided
            RobinhoodAPIError: If the request fails

        Example:
            >>> from robinhood_enum import OrderSide, TimeInForce
            >>> client = OrdersClient()
            >>>
            >>> # Buy Bitcoin only if price drops to $45,000
            >>> order = client.place_limit_order(
            ...     symbol="BTC-USD",
            ...     side=OrderSide.BUY,
            ...     limit_price=45000.0,
            ...     asset_quantity=0.01,
            ...     time_in_force=TimeInForce.GTC
            ... )
        """
        if not asset_quantity and not quote_amount:
            raise RobinhoodValidationError(
                "Either asset_quantity or quote_amount must be provided"
            )
        if asset_quantity and quote_amount:
            raise RobinhoodValidationError(
                "Only one of asset_quantity or quote_amount can be provided"
            )

        limit_config = {
            "limit_price": str(limit_price),
            "time_in_force": time_in_force.value,
        }
        if asset_quantity:
            limit_config["asset_quantity"] = str(asset_quantity)
        if quote_amount:
            limit_config["quote_amount"] = str(quote_amount)

        body = {
            "client_order_id": client_order_id or str(uuid.uuid4()),
            "side": side.value,
            "type": OrderType.LIMIT.value,
            "symbol": symbol.upper(),
            "limit_order_config": limit_config,
        }

        return self.make_request("POST", "/api/v1/crypto/trading/orders/", body)

    def place_stop_loss_order(
        self,
        symbol: str,
        side: OrderSide,
        stop_price: float,
        asset_quantity: Optional[float] = None,
        quote_amount: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place a stop loss order to limit losses.

        Stop loss orders become market orders when the stop price is reached,
        helping to limit losses on existing positions.

        Args:
            symbol: Trading pair symbol
            side: Order side (usually SELL for stop losses)
            stop_price: Price that triggers the order
            asset_quantity: Amount of cryptocurrency to trade
            quote_amount: USD amount to trade
            time_in_force: How long the order remains active
            client_order_id: Optional client-provided order ID

        Returns:
            Dict[str, Any]: Order response with order details

        Raises:
            RobinhoodValidationError: If neither or both quantities are provided
            RobinhoodAPIError: If the request fails

        Example:
            >>> from robinhood_enum import OrderSide
            >>> client = OrdersClient()
            >>>
            >>> # Stop loss: sell Bitcoin if price drops to $40,000
            >>> order = client.place_stop_loss_order(
            ...     symbol="BTC-USD",
            ...     side=OrderSide.SELL,
            ...     stop_price=40000.0,
            ...     asset_quantity=0.01
            ... )
        """
        if not asset_quantity and not quote_amount:
            raise RobinhoodValidationError(
                "Either asset_quantity or quote_amount must be provided"
            )
        if asset_quantity and quote_amount:
            raise RobinhoodValidationError(
                "Only one of asset_quantity or quote_amount can be provided"
            )

        stop_config = {
            "stop_price": str(stop_price),
            "time_in_force": time_in_force.value,
        }
        if asset_quantity:
            stop_config["asset_quantity"] = str(asset_quantity)
        if quote_amount:
            stop_config["quote_amount"] = str(quote_amount)

        body = {
            "client_order_id": client_order_id or str(uuid.uuid4()),
            "side": side.value,
            "type": OrderType.STOP_LOSS.value,
            "symbol": symbol.upper(),
            "stop_loss_order_config": stop_config,
        }

        return self.make_request("POST", "/api/v1/crypto/trading/orders/", body)

    def place_stop_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        stop_price: float,
        limit_price: float,
        asset_quantity: Optional[float] = None,
        quote_amount: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place a stop limit order combining stop and limit functionality.

        Stop limit orders become limit orders when the stop price is reached,
        providing both trigger control and execution price control.

        Args:
            symbol: Trading pair symbol
            side: Order side
            stop_price: Price that triggers the order
            limit_price: Limit price for execution after trigger
            asset_quantity: Amount of cryptocurrency to trade
            quote_amount: USD amount to trade
            time_in_force: How long the order remains active
            client_order_id: Optional client-provided order ID

        Returns:
            Dict[str, Any]: Order response with order details

        Raises:
            RobinhoodValidationError: If neither or both quantities are provided
            RobinhoodAPIError: If the request fails

        Example:
            >>> from robinhood_enum import OrderSide
            >>> client = OrdersClient()
            >>>
            >>> # Stop limit: if BTC drops to $40,000, sell at $39,500 or better
            >>> order = client.place_stop_limit_order(
            ...     symbol="BTC-USD",
            ...     side=OrderSide.SELL,
            ...     stop_price=40000.0,
            ...     limit_price=39500.0,
            ...     asset_quantity=0.01
            ... )
        """
        if not asset_quantity and not quote_amount:
            raise RobinhoodValidationError(
                "Either asset_quantity or quote_amount must be provided"
            )
        if asset_quantity and quote_amount:
            raise RobinhoodValidationError(
                "Only one of asset_quantity or quote_amount can be provided"
            )

        stop_limit_config = {
            "stop_price": str(stop_price),
            "limit_price": str(limit_price),
            "time_in_force": time_in_force.value,
        }
        if asset_quantity:
            stop_limit_config["asset_quantity"] = str(asset_quantity)
        if quote_amount:
            stop_limit_config["quote_amount"] = str(quote_amount)

        body = {
            "client_order_id": client_order_id or str(uuid.uuid4()),
            "side": side.value,
            "type": OrderType.STOP_LIMIT.value,
            "symbol": symbol.upper(),
            "stop_limit_order_config": stop_limit_config,
        }

        return self.make_request("POST", "/api/v1/crypto/trading/orders/", body)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an open order.

        Cancels an existing order that is still open or partially filled.
        Only orders in cancellable states can be cancelled.

        Args:
            order_id: ID of the order to cancel

        Returns:
            Dict[str, Any]: Cancellation response

        Raises:
            RobinhoodAPIError: If the request fails or order cannot be cancelled

        Example:
            >>> client = OrdersClient()
            >>>
            >>> # Place an order
            >>> order = client.place_limit_order(...)
            >>> order_id = order['id']
            >>>
            >>> # Cancel the order
            >>> result = client.cancel_order(order_id)
            >>> print(f"Cancellation result: {result}")
        """
        if not order_id:
            raise RobinhoodValidationError("Order ID is required")

        path = f"/api/v1/crypto/trading/orders/{order_id}/cancel/"
        return self.make_request("POST", path)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all currently open orders.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            List[Dict[str, Any]]: List of open orders
        """
        return self.get_all_orders_paginated(state=OrderState.OPEN, symbol=symbol)

    def get_filled_orders(
        self, symbol: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recently filled orders.

        Args:
            symbol: Optional symbol to filter by
            limit: Optional limit on number of orders

        Returns:
            List[Dict[str, Any]]: List of filled orders
        """
        if limit:
            response = self.get_orders(
                state=OrderState.FILLED, symbol=symbol, limit=limit
            )
            return response.get("results", [])
        else:
            return self.get_all_orders_paginated(state=OrderState.FILLED, symbol=symbol)

    def cancel_all_open_orders(
        self, symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Cancel all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter orders

        Returns:
            List[Dict[str, Any]]: List of cancellation results

        Raises:
            RobinhoodAPIError: If any cancellation fails
        """
        open_orders = self.get_open_orders(symbol)
        results = []

        for order in open_orders:
            try:
                result = self.cancel_order(order["id"])
                results.append(
                    {
                        "order_id": order["id"],
                        "symbol": order["symbol"],
                        "success": True,
                        "result": result,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "order_id": order["id"],
                        "symbol": order["symbol"],
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    def get_order_status(self, order_id: str) -> str:
        """
        Get the current status of an order.

        Args:
            order_id: Order ID to check

        Returns:
            str: Order state (e.g., "open", "filled", "canceled")
        """
        order = self.get_order(order_id)
        return order.get("state", "unknown")

    def is_order_filled(self, order_id: str) -> bool:
        """
        Check if an order is completely filled.

        Args:
            order_id: Order ID to check

        Returns:
            bool: True if order is filled
        """
        status = self.get_order_status(order_id)
        return status.lower() == "filled"

    def is_order_open(self, order_id: str) -> bool:
        """
        Check if an order is still open.

        Args:
            order_id: Order ID to check

        Returns:
            bool: True if order is open
        """
        status = self.get_order_status(order_id)
        return status.lower() in ["open", "partially_filled"]
