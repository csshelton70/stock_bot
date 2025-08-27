# scripts/run_collector.py
#!/usr/bin/env python3
"""
Refactored data collection runner script
"""

# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation

import sys

from apps.data_collector_app import DataCollectorApp 


def main() -> int:
    """Main entry point for data collection"""
    app = DataCollectorApp()
    f_exit_code = app.run()
    return f_exit_code


if __name__ == "__main__":
    exit_code:int = main()
    sys.exit(exit_code)
