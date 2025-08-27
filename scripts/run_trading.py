# scripts/run_trading.py
#!/usr/bin/env python3
"""
Refactored trading system runner script
"""

import sys

from apps.trading_system_app import TradingSystemApp


def main()->int:
    """Main entry point for trading system"""
    app = TradingSystemApp()
    f_exit_code = app.run()
    return f_exit_code


if __name__ == "__main__":
    exit_code:int = main()
    sys.exit(exit_code)
