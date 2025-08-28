#!/usr/bin/env python3
"""
Robinhood Crypto API Example Usage Script
=========================================

This script demonstrates how to use the Robinhood Crypto API Python library
with various real-world examples including account management, market data
retrieval, and order placement.

Setup:
1. Generate API keypair: python example_usage.py --generate-keys
2. Create config file: python example_usage.py --create-config
3. Edit config.json with your API credentials
4. Run the demo: python example_usage.py

Author: Robinhood Crypto API Integration
Version: 1.0.0
"""

import os
import sys
from utils.logger import get_logger
import json
from pathlib import Path

# Import the Robinhood API library
from robinhood_helper import (
    create_client,
    generate_keypair,
    get_setup_guide,
    create_config_file,
)
from robinhood_config import RobinhoodConfig
from robinhood_enum import (
    EstimatedPriceSide,
)
from robinhood_error import (
    RobinhoodAuthError,
    RobinhoodValidationError,
)

# pylint:disable=f-string-without-interpolation,broad-exception-caught,line-too-long


def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def check_configuration_setup():
    """Check if configuration is properly set up."""
    config_paths = [
        "config.json",
        "robinhood_config.json",
        os.path.expanduser("~/.robinhood/config.json"),
        os.path.expanduser("~/.config/robinhood/config.json"),
    ]

    config_file = None
    for path in config_paths:
        if os.path.exists(path):
            config_file = path
            break

    if not config_file:
        print("❌ No configuration file found")
        print("Searched in:")
        for path in config_paths:
            print(f"   - {path}")
        print("\n💡 Run with --create-config to create a configuration file")
        return False, None

    # Try to load and validate the configuration
    try:
        config = RobinhoodConfig.from_json_file(config_file)
        if not config.api_key or config.api_key == "your_api_key_here":
            print(f"❌ Configuration file found at {config_file} but API key not set")
            print(
                "💡 Please edit the configuration file with your actual API credentials"
            )
            return False, config_file

        if (
            not config.private_key_base64
            or config.private_key_base64 == "your_base64_private_key_here"
        ):
            print(
                f"❌ Configuration file found at {config_file} but private key not set"
            )
            print(
                "💡 Please edit the configuration file with your actual API credentials"
            )
            return False, config_file

        print(f"✅ Configuration loaded from: {config_file}")
        masked_config = config.mask_sensitive_data()
        print(f"   API Key: {masked_config['api_key']}")
        print(f"   Base URL: {masked_config['base_url']}")
        print(f"   Log Level: {masked_config['log_level']}")
        return True, config_file

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in configuration file {config_file}: {e}")
        return False, config_file
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return False, config_file


def generate_api_keypair():
    """Generate a new API keypair for first-time setup."""
    print("🔑 Generating new API keypair...")
    try:
        private_key, public_key = generate_keypair()
        print(f"✅ Keypair generated successfully!")
        print(f"\nPrivate Key (keep this secret): {private_key}")
        print(f"Public Key (register with Robinhood): {public_key}")
        print("\n📝 Next steps:")
        print("1. Go to https://robinhood.com/crypto/api")
        print("2. Create new API credentials using the public key above")
        print(
            "3. Run 'python example_usage.py --create-config' to create configuration file"
        )
        print("4. Edit config.json with your API key and the private key above")
        return True
    except Exception as e:
        print(f"❌ Failed to generate keypair: {e}")
        return False


def create_configuration_file():
    """Create a configuration file interactively."""
    print("📝 Creating configuration file...")
    try:
        create_config_file(interactive=True)
        print("✅ Configuration file created successfully!")
        print("💡 You can now run the demo with: python example_usage.py")
        return True
    except Exception as e:
        print(f"❌ Failed to create configuration file: {e}")
        return False


def test_api_connection():
    """Test basic API connectivity and authentication."""
    print("🔍 Testing API connection...")
    try:
        with create_client() as client:
            # Perform health check
            if client.health_check():
                print("✅ API connection successful")
                return True
            else:
                print("❌ API health check failed")
                return False

    except RobinhoodAuthError as e:
        print(f"❌ Authentication failed: {e}")
        print("💡 Check your API key and private key in the configuration file")
        return False
    except FileNotFoundError as e:
        print(f"❌ Configuration file not found: {e}")
        print("💡 Run with --create-config to create a configuration file")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


def demonstrate_account_info():
    """Demonstrate getting account information."""
    print("\n📋 Getting Account Information")
    print("=" * 50)

    try:
        with create_client() as client:
            account = client.get_account()

            print(f"Account Number: {account.get('account_number', 'N/A')}")
            print(f"Status: {account.get('status', 'N/A')}")
            print(f"Buying Power: ${account.get('buying_power', '0')}")
            print(f"Currency: {account.get('buying_power_currency', 'USD')}")

    except Exception as e:
        print(f"❌ Failed to get account info: {e}")


def demonstrate_market_data():
    """Demonstrate market data retrieval."""
    print("\n📈 Getting Market Data")
    print("=" * 50)

    symbols = ["BTC-USD", "ETH-USD", "ADA-USD"]

    try:
        with create_client() as client:
            # Get trading pairs info
            print("Trading Pairs:")
            trading_pairs = client.get_trading_pairs(symbols)
            for pair in trading_pairs.get("results", []):
                symbol = pair.get("symbol", "Unknown")
                min_size = pair.get("min_order_size", "N/A")
                max_size = pair.get("max_order_size", "N/A")
                print(f"  {symbol}: Min={min_size}, Max={max_size}")

            # Get current prices
            print("\nCurrent Prices:")
            prices = client.get_best_bid_ask(symbols)
            for price_data in prices.get("results", []):
                symbol = price_data.get("symbol", "Unknown")
                bid = float(price_data.get("bid_price", 0))
                ask = float(price_data.get("ask_price", 0))
                spread = ask - bid
                spread_pct = (spread / bid * 100) if bid > 0 else 0

                print(
                    f"  {symbol}: Bid=${bid:,.2f}, Ask=${ask:,.2f}, Spread=${spread:.2f} ({spread_pct:.2f}%)"
                )

            # Get estimated prices for different quantities
            print(f"\nEstimated Prices for BTC-USD:")
            quantities = [0.001, 0.01, 0.1]
            estimates = client.get_estimated_price(
                symbol="BTC-USD", side=EstimatedPriceSide.ASK, quantities=quantities
            )

            for result in estimates.get("results", []):
                qty = result.get("quantity", 0)
                price = float(result.get("price", 0))
                total = float(qty) * price
                print(f"  Buy {qty} BTC ≈ ${price:,.2f} each = ${total:,.2f} total")

    except Exception as e:
        print(f"❌ Failed to get market data: {e}")


def demonstrate_holdings():
    """Demonstrate getting crypto holdings."""
    print("\n💼 Getting Holdings")
    print("=" * 50)

    try:
        with create_client() as client:
            holdings = client.get_all_holdings_paginated()

            if not holdings:
                print("No holdings found")
                return

            total_positions = 0
            for holding in holdings:
                asset_code = holding.get("asset_code", "Unknown")
                quantity = float(holding.get("total_quantity", 0))

                if quantity > 0:
                    total_positions += 1
                    print(f"  {asset_code}: {quantity:.8f}")

            print(f"\nTotal positions: {total_positions}")

    except Exception as e:
        print(f"❌ Failed to get holdings: {e}")


def demonstrate_order_history():
    """Demonstrate getting order history."""
    print("\n📜 Getting Order History")
    print("=" * 50)

    try:
        with create_client() as client:
            # Get recent orders
            orders = client.get_orders(limit=10)

            order_list = orders.get("results", [])
            if not order_list:
                print("No orders found")
                return

            print(f"Showing last {len(order_list)} orders:")
            for order in order_list:
                order_id = order.get("id", "Unknown")[:8]
                symbol = order.get("symbol", "Unknown")
                side = order.get("side", "Unknown")
                order_type = order.get("type", "Unknown")
                state = order.get("state", "Unknown")
                created_at = order.get("created_at", "Unknown")

                print(
                    f"  {order_id}: {side.upper()} {symbol} ({order_type}) - {state} @ {created_at[:19]}"
                )

    except Exception as e:
        print(f"❌ Failed to get order history: {e}")


def demonstrate_order_placement_simulation():
    """Demonstrate order placement (simulation only - doesn't actually place orders)."""
    print("\n🔄 Order Placement Examples (SIMULATION)")
    print("=" * 50)
    print("⚠️  These are examples only - no actual orders will be placed")

    try:
        with create_client() as client:  # pylint:disable=unused-variable
            # Example 1: Market Order
            print("\nExample Market Order:")
            print("  Symbol: BTC-USD")
            print("  Side: BUY")
            print("  Amount: $10.00")
            print("  Type: MARKET")

            # Uncomment to actually place order (BE VERY CAREFUL!)
            # market_order = client.place_market_order(
            #     symbol="BTC-USD",
            #     side=OrderSide.BUY,
            #     quote_amount=10.0
            # )
            # print(f"✅ Market order placed: {market_order.get('id')}")

            # Example 2: Limit Order
            print("\nExample Limit Order:")
            print("  Symbol: ETH-USD")
            print("  Side: BUY")
            print("  Quantity: 0.01 ETH")
            print("  Limit Price: $2000.00")
            print("  Time in Force: GTC")

            # Uncomment to actually place order (BE VERY CAREFUL!)
            # limit_order = client.place_limit_order(
            #     symbol="ETH-USD",
            #     side=OrderSide.BUY,
            #     limit_price=2000.0,
            #     asset_quantity=0.01,
            #     time_in_force=TimeInForce.GTC
            # )
            # print(f"✅ Limit order placed: {limit_order.get('id')}")

            print("\n💡 To enable actual order placement:")
            print("   1. Uncomment the order placement code above")
            print("   2. Be very careful with amounts and prices")
            print("   3. Start with very small test amounts")

    except Exception as e:
        print(f"❌ Order placement simulation failed: {e}")


def demonstrate_configuration_management():
    """Demonstrate configuration file management."""
    print("\n⚙️  Configuration Management")
    print("=" * 50)

    try:
        # Show current configuration (masked)
        config = RobinhoodConfig.from_json_file()
        masked_config = config.mask_sensitive_data()

        print("Current Configuration:")
        for key, value in masked_config.items():
            print(f"  {key}: {value}")

        # Show configuration file locations
        print("\nSupported configuration file locations:")
        config_paths = [
            "./config.json",
            "./robinhood_config.json",
            "~/.robinhood/config.json",
            "~/.config/robinhood/config.json",
        ]

        for path in config_paths:
            expanded_path = os.path.expanduser(path)
            exists = "✅" if os.path.exists(expanded_path) else "❌"
            print(f"  {exists} {path}")

        # Show how to create example config
        print("\n💡 Configuration Management Commands:")
        print(
            "  python example_usage.py --create-config     # Create config interactively"
        )
        print(
            "  python example_usage.py --example-config    # Create config.example.json"
        )

    except Exception as e:
        print(f"❌ Configuration management demonstration failed: {e}")


def demonstrate_error_handling():
    """Demonstrate comprehensive error handling."""
    print("\n🛡️  Error Handling Examples")
    print("=" * 50)

    try:
        with create_client() as client:
            # Example 1: Invalid symbol validation
            try:
                client.get_best_bid_ask(["INVALID-SYMBOL"])
            except RobinhoodValidationError as e:
                print(f"✅ Caught validation error: {e}")

            # Example 2: Rate limit handling
            print("✅ Server-side rate limiting is handled automatically")
            print("   The library will retry with exponential backoff on 429 responses")

            # Example 3: Network error simulation
            print("✅ Network errors are handled with automatic retries")
            print("   Max retries: 3, Backoff factor: 0.3")

    except Exception as e:
        print(f"❌ Error handling demonstration failed: {e}")


def demonstrate_advanced_features():
    """Demonstrate advanced features like pagination and context management."""
    print("\n🚀 Advanced Features")
    print("=" * 50)

    try:
        # Context manager usage
        print("✅ Using context manager for automatic resource cleanup")
        with create_client() as client:
            print("   Client created and will be automatically closed")

            # Pagination example
            print("✅ Pagination support for large datasets")
            all_orders = client.get_all_orders_paginated()
            print(f"   Retrieved {len(all_orders)} total orders across all pages")

            # Custom configuration
            print("✅ Custom configuration support")
            print(f"   Request timeout: {client.config.request_timeout} seconds")
            print(f"   Max retries: {client.config.max_retries}")
            print(f"   Backoff factor: {client.config.backoff_factor}")

    except Exception as e:
        print(f"❌ Advanced features demonstration failed: {e}")


def show_help():
    """Show help information."""
    print("Robinhood Crypto API Python Library - Example Usage")
    print("=" * 60)
    print("\nUsage:")
    print("  python example_usage.py                    # Run full demo")
    print("  python example_usage.py --generate-keys    # Generate new keypair")
    print(
        "  python example_usage.py --create-config    # Create config file interactively"
    )
    print("  python example_usage.py --example-config   # Create config.example.json")
    print("  python example_usage.py --setup-guide      # Show setup instructions")
    print("  python example_usage.py --help             # Show this help")
    print("\nConfiguration:")
    print("  The library uses JSON configuration files by default.")
    print("  Configuration files are searched in this order:")
    print("    1. ./config.json")
    print("    2. ./robinhood_config.json")
    print("    3. ~/.robinhood/config.json")
    print("    4. ~/.config/robinhood/config.json")
    print("\nFirst time setup:")
    print("  1. python example_usage.py --generate-keys")
    print("  2. python example_usage.py --create-config")
    print("  3. Edit config.json with your API credentials")
    print("  4. python example_usage.py")


def main():
    """Main demonstration function."""
    print("🏦 Robinhood Crypto API Python Library Demo")
    print("=" * 60)

    setup_logging()

    # Check command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == "--generate-keys":
            generate_api_keypair()
            return
        elif arg == "--create-config":
            create_configuration_file()
            return
        elif arg == "--example-config":
            try:
                RobinhoodConfig.create_example_config()
            except Exception as e:
                print(f"❌ Failed to create example config: {e}")
            return
        elif arg == "--setup-guide":
            print(get_setup_guide())
            return
        elif arg == "--help":
            show_help()
            return
        else:
            print(f"❌ Unknown argument: {arg}")
            show_help()
            return

    # Check configuration setup
    config_ok, config_file = check_configuration_setup()
    if not config_ok:
        print("\n💡 Setup commands:")
        print("  python example_usage.py --generate-keys    # Generate API keypair")
        print(
            "  python example_usage.py --create-config    # Create configuration file"
        )
        print(
            "  python example_usage.py --setup-guide      # Show detailed setup guide"
        )
        return

    # Test API connection
    if not test_api_connection():
        return

    # Run demonstrations
    demonstrate_account_info()
    demonstrate_market_data()
    demonstrate_holdings()
    demonstrate_order_history()
    demonstrate_order_placement_simulation()
    demonstrate_configuration_management()
    demonstrate_error_handling()
    demonstrate_advanced_features()

    print("\n✅ Demo completed successfully!")
    print(f"\n📁 Configuration loaded from: {config_file}")
    print("\n📚 Next steps:")
    print("   1. Review the code in this example")
    print("   2. Read the README.md for detailed documentation")
    print("   3. Start building your own trading applications")
    print("   4. Always test with small amounts first!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with unexpected error: {e}")
        import traceback

        traceback.print_exc()
