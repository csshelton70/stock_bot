# scripts/run_collector.py
#!/usr/bin/env python3
"""
Refactored data collection runner script
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.data_collector_app import DataCollectorApp


def main():
    """Main entry point for data collection"""
    app = DataCollectorApp()
    exit_code = app.run()
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
