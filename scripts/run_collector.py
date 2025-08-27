# scripts/run_collector.py
#!/usr/bin/env python3
"""
Refactored data collection runner script
"""

# pylint:disable=broad-exception-caught,trailing-whitespace,line-too-long,logging-fstring-interpolation, import-outside-toplevel

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main() -> int:
    """Main entry point for data collection"""
    from apps import DataCollectorApp 

    app = DataCollectorApp()
    f_exit_code = app.run()
    return f_exit_code


if __name__ == "__main__":
    exit_code:int = main()
    sys.exit(exit_code)
