# scripts/run_trading.py
#!/usr/bin/env python3
"""
Refactored trading system runner script
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.trading_system_app import TradingSystemApp


def main():
    """Main entry point for trading system"""
    app = TradingSystemApp()
    exit_code = app.run()
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
