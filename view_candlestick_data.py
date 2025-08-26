#!/usr/bin/env python3
# ./view_candlestick_data.py
"""
Candlestick Data Viewer for Robinhood Crypto Trading App
======================================================

This script displays historical candlestick (OHLCV) data for a specified crypto symbol
from your database. It can show data in various formats and time ranges.

Usage:
    python view_candlestick_data.py --symbol BTC-USD
    python view_candlestick_data.py --symbol ETH-USD --days 30
    python view_candlestick_data.py --symbol BTC-USD --format csv
    python view_candlestick_data.py --symbol SOL-USD --latest 10
    python view_candlestick_data.py --list-symbols

Options:
    --symbol SYMBOL     Crypto symbol to display (e.g., BTC-USD)
    --days DAYS         Number of days to show (default: 60)
    --latest N          Show only the latest N records
    --format FORMAT     Output format: table, csv, json (default: table)
    --list-symbols      List all available symbols in database
    --stats             Show summary statistics
    --export FILE       Export data to file (CSV format)

Examples:
    # View BTC data for last 60 days
    python view_candlestick_data.py --symbol BTC-USD

    # View ETH data for last 30 days in CSV format
    python view_candlestick_data.py --symbol ETH-USD --days 30 --format csv

    # Show latest 20 records with stats
    python view_candlestick_data.py --symbol PEPE-USD --latest 20 --stats

    # Export to CSV file
    python view_candlestick_data.py --symbol BTC-USD --export btc_data.csv

Author: Robinhood Crypto Trading App
Version: 1.0.0
"""

import sys
import os
import logging
import argparse
import json
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import Config
from database import DatabaseManager, DatabaseSession
from database import Historical, Crypto
from sqlalchemy import and_, desc, func

# Setup logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise for data viewing
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("candlestick_viewer")


class CandlestickDataViewer:
    """Views and analyzes historical candlestick data"""

    def __init__(self, config_path: str = "config.json"):
        try:
            self.config = Config(config_path)
        except FileNotFoundError:
            logger.warning("Config file not found, using default database path")
            self.db_path = "crypto_trading.db"
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.db_path = "crypto_trading.db"
        else:
            self.db_path = self.config.database_path

        self.db_manager = DatabaseManager(self.db_path)

    def get_available_symbols(self) -> List[str]:
        """Get list of symbols that have historical data"""
        try:
            with DatabaseSession(self.db_manager) as session:
                # Get distinct symbols from historical table
                result = (
                    session.query(Historical.symbol)
                    .distinct()
                    .order_by(Historical.symbol)
                    .all()
                )
                symbols = [row[0] for row in result]
                return symbols
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return []

    def get_symbol_data_info(self, symbol: str) -> Dict[str, Any]:
        """Get information about available data for a symbol"""
        try:
            with DatabaseSession(self.db_manager) as session:
                # Get data range and count
                result = (
                    session.query(
                        func.min(Historical.timestamp),
                        func.max(Historical.timestamp),
                        func.count(Historical.id),
                    )
                    .filter(Historical.symbol == symbol.upper())
                    .first()
                )

                if not result or not result[0]:
                    return {"exists": False}

                min_date, max_date, count = result

                return {
                    "exists": True,
                    "symbol": symbol.upper(),
                    "earliest_date": min_date,
                    "latest_date": max_date,
                    "total_records": count,
                    "date_range_days": (
                        (max_date - min_date).days if min_date and max_date else 0
                    ),
                }
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return {"exists": False, "error": str(e)}

    def get_candlestick_data(
        self, symbol: str, days: Optional[int] = None, latest: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get candlestick data for a symbol

        Args:
            symbol: Crypto symbol (e.g., BTC-USD)
            days: Number of days back to retrieve (default: all)
            latest: Number of latest records to retrieve (overrides days)

        Returns:
            List of historical records as dictionaries
        """
        try:
            with DatabaseSession(self.db_manager) as session:
                query = session.query(Historical).filter(
                    Historical.symbol == symbol.upper()
                )

                if latest:
                    # Get latest N records
                    query = query.order_by(desc(Historical.timestamp)).limit(latest)
                    records = query.all()
                    # Reverse to show chronological order
                    records = list(reversed(records))
                elif days:
                    # Get records from N days ago
                    cutoff_date = datetime.now() - timedelta(days=days)
                    query = query.filter(Historical.timestamp >= cutoff_date)
                    records = query.order_by(Historical.timestamp).all()
                else:
                    # Get all records
                    records = query.order_by(Historical.timestamp).all()

                # Convert to dictionaries
                data = []
                for record in records:
                    data.append(
                        {
                            "timestamp": record.timestamp,
                            "open": record.open,
                            "high": record.high,
                            "low": record.low,
                            "close": record.close,
                            "volume": record.volume,
                        }
                    )

                return data

        except Exception as e:
            logger.error(f"Error getting candlestick data for {symbol}: {e}")
            return []

    def calculate_statistics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics for the data"""
        if not data:
            return {}

        prices = []
        volumes = []
        daily_changes = []

        for i, record in enumerate(data):
            prices.extend(
                [record["open"], record["high"], record["low"], record["close"]]
            )
            volumes.append(record["volume"])

            if i > 0:
                prev_close = data[i - 1]["close"]
                change_pct = ((record["close"] - prev_close) / prev_close) * 100
                daily_changes.append(change_pct)

        return {
            "records_count": len(data),
            "date_range": {
                "start": data[0]["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                "end": data[-1]["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                "days": (data[-1]["timestamp"] - data[0]["timestamp"]).days,
            },
            "price_stats": {
                "min": min(prices),
                "max": max(prices),
                "first_close": data[0]["close"],
                "last_close": data[-1]["close"],
                "total_change": data[-1]["close"] - data[0]["close"],
                "total_change_pct": (
                    (data[-1]["close"] - data[0]["close"]) / data[0]["close"]
                )
                * 100,
            },
            "volume_stats": {
                "min": min(volumes),
                "max": max(volumes),
                "avg": sum(volumes) / len(volumes),
                "total": sum(volumes),
            },
            "volatility": {
                "avg_daily_change": (
                    sum(abs(change) for change in daily_changes) / len(daily_changes)
                    if daily_changes
                    else 0
                ),
                "max_daily_gain": max(daily_changes) if daily_changes else 0,
                "max_daily_loss": min(daily_changes) if daily_changes else 0,
            },
        }

    def format_table_output(self, data: List[Dict[str, Any]], symbol: str) -> str:
        """Format data as a readable table"""
        if not data:
            return f"No data found for {symbol}"

        output = [f"\n📊 Candlestick Data for {symbol.upper()}"]
        output.append("=" * 80)
        output.append(
            f"{'Date':<20} {'Open':<12} {'High':<12} {'Low':<12} {'Close':<12} {'Volume':<15}"
        )
        output.append("-" * 80)

        for record in data:
            date_str = record["timestamp"].strftime("%Y-%m-%d %H:%M")
            output.append(
                f"{date_str:<20} "
                f"${record['open']:<11.6f} "
                f"${record['high']:<11.6f} "
                f"${record['low']:<11.6f} "
                f"${record['close']:<11.6f} "
                f"{record['volume']:<15,.0f}"
            )

        return "\n".join(output)

    def format_csv_output(self, data: List[Dict[str, Any]]) -> str:
        """Format data as CSV"""
        if not data:
            return "No data available"

        lines = ["timestamp,open,high,low,close,volume"]
        for record in data:
            lines.append(
                f"{record['timestamp'].isoformat()},"
                f"{record['open']:.6f},"
                f"{record['high']:.6f},"
                f"{record['low']:.6f},"
                f"{record['close']:.6f},"
                f"{record['volume']:.0f}"
            )

        return "\n".join(lines)

    def format_json_output(self, data: List[Dict[str, Any]]) -> str:
        """Format data as JSON"""
        # Convert datetime objects to ISO strings for JSON serialization
        json_data = []
        for record in data:
            json_record = record.copy()
            json_record["timestamp"] = record["timestamp"].isoformat()
            json_data.append(json_record)

        return json.dumps(json_data, indent=2)

    def format_statistics_output(self, stats: Dict[str, Any], symbol: str) -> str:
        """Format statistics as readable output"""
        if not stats:
            return "No statistics available"

        output = [f"\n📈 Statistics for {symbol.upper()}"]
        output.append("=" * 50)

        # Date range
        output.append(f"📅 Date Range:")
        output.append(f"   From: {stats['date_range']['start']}")
        output.append(f"   To:   {stats['date_range']['end']}")
        output.append(f"   Days: {stats['date_range']['days']}")
        output.append(f"   Records: {stats['records_count']:,}")

        # Price statistics
        output.append(f"\n💰 Price Statistics:")
        output.append(
            f"   Range: ${stats['price_stats']['min']:.6f} - ${stats['price_stats']['max']:.6f}"
        )
        output.append(f"   First Close: ${stats['price_stats']['first_close']:.6f}")
        output.append(f"   Last Close:  ${stats['price_stats']['last_close']:.6f}")
        output.append(
            f"   Total Change: ${stats['price_stats']['total_change']:+.6f} ({stats['price_stats']['total_change_pct']:+.2f}%)"
        )

        # Volume statistics
        output.append(f"\n📊 Volume Statistics:")
        output.append(
            f"   Range: {stats['volume_stats']['min']:,.0f} - {stats['volume_stats']['max']:,.0f}"
        )
        output.append(f"   Average: {stats['volume_stats']['avg']:,.0f}")
        output.append(f"   Total: {stats['volume_stats']['total']:,.0f}")

        # Volatility
        output.append(f"\n📈 Volatility:")
        output.append(
            f"   Avg Daily Change: {stats['volatility']['avg_daily_change']:.2f}%"
        )
        output.append(
            f"   Max Daily Gain: {stats['volatility']['max_daily_gain']:+.2f}%"
        )
        output.append(
            f"   Max Daily Loss: {stats['volatility']['max_daily_loss']:+.2f}%"
        )

        return "\n".join(output)

    def export_to_csv(self, data: List[Dict[str, Any]], filename: str) -> bool:
        """Export data to CSV file"""
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                if not data:
                    f.write("No data available\n")
                    return True

                writer = csv.writer(f)
                writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])

                for record in data:
                    writer.writerow(
                        [
                            record["timestamp"].isoformat(),
                            f"{record['open']:.6f}",
                            f"{record['high']:.6f}",
                            f"{record['low']:.6f}",
                            f"{record['close']:.6f}",
                            f"{record['volume']:.0f}",
                        ]
                    )

            print(f"✅ Data exported to {filename}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to {filename}: {e}")
            return False

    def list_available_symbols(self) -> str:
        """List all available symbols with data info"""
        symbols = self.get_available_symbols()

        if not symbols:
            return "No symbols found in database"

        output = [f"\n📋 Available Symbols ({len(symbols)} total)"]
        output.append("=" * 70)
        output.append(f"{'Symbol':<15} {'Records':<10} {'Date Range':<25} {'Days':<8}")
        output.append("-" * 70)

        for symbol in symbols:
            info = self.get_symbol_data_info(symbol)
            if info["exists"]:
                date_range = f"{info['earliest_date'].strftime('%Y-%m-%d')} to {info['latest_date'].strftime('%Y-%m-%d')}"
                output.append(
                    f"{symbol:<15} {info['total_records']:<10,} {date_range:<25} {info['date_range_days']:<8}"
                )

        return "\n".join(output)

    def cleanup(self):
        """Cleanup database connections"""
        if hasattr(self, "db_manager"):
            self.db_manager.close()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="View historical candlestick data for crypto symbols",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python view_candlestick_data.py --symbol BTC-USD
  python view_candlestick_data.py --symbol ETH-USD --days 30 --stats
  python view_candlestick_data.py --symbol PEPE-USD --latest 20 --format csv
  python view_candlestick_data.py --list-symbols
  python view_candlestick_data.py --symbol BTC-USD --export btc_data.csv
        """,
    )

    parser.add_argument("--symbol", type=str, help="Crypto symbol (e.g., BTC-USD)")
    parser.add_argument(
        "--days", type=int, default=60, help="Number of days to show (default: 60)"
    )
    parser.add_argument("--latest", type=int, help="Show only the latest N records")
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format",
    )
    parser.add_argument("--stats", action="store_true", help="Show summary statistics")
    parser.add_argument(
        "--list-symbols", action="store_true", help="List all available symbols"
    )
    parser.add_argument("--export", type=str, help="Export data to CSV file")
    parser.add_argument("--config", default="config.json", help="Config file path")

    args = parser.parse_args()

    # Validate arguments
    if not args.list_symbols and not args.symbol:
        parser.error("Must specify --symbol or --list-symbols")

    viewer = None
    try:
        print("📊 Robinhood Crypto Candlestick Data Viewer")
        print("=" * 50)

        # Initialize viewer
        viewer = CandlestickDataViewer(args.config)

        # Handle list symbols
        if args.list_symbols:
            print(viewer.list_available_symbols())
            return 0

        # Validate symbol exists
        symbol = args.symbol.upper()
        info = viewer.get_symbol_data_info(symbol)

        if not info["exists"]:
            print(f"❌ No data found for symbol: {symbol}")
            print("\nAvailable symbols:")
            available = viewer.get_available_symbols()
            if available:
                print(", ".join(available))
            else:
                print("No symbols available in database")
            return 1

        # Get the data
        print(f"📥 Loading data for {symbol}...")
        data = viewer.get_candlestick_data(symbol, args.days, args.latest)

        if not data:
            print(f"❌ No data retrieved for {symbol}")
            return 1

        # Export if requested
        if args.export:
            if viewer.export_to_csv(data, args.export):
                print(f"✅ Data exported to {args.export}")
            else:
                print(f"❌ Failed to export data")
                return 1

        # Display data in requested format
        if args.format == "table":
            print(viewer.format_table_output(data, symbol))
        elif args.format == "csv":
            print(viewer.format_csv_output(data))
        elif args.format == "json":
            print(viewer.format_json_output(data))

        # Show statistics if requested
        if args.stats:
            stats = viewer.calculate_statistics(data)
            print(viewer.format_statistics_output(stats, symbol))

        return 0

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Application failed: {e}")
        print(f"❌ Error: {e}")
        return 1

    finally:
        if viewer:
            viewer.cleanup()


if __name__ == "__main__":
    sys.exit(main())
