#!/usr/bin/env python3
"""
Interactive Candlestick Chart Viewer for Robinhood Crypto Trading App
====================================================================

This script creates beautiful, interactive candlestick charts for crypto symbols
from your database using Plotly. Charts can be displayed in browser, saved as images,
or exported as HTML files.

Usage:
    python candlestick_chart_viewer.py --symbol BTC-USD
    python candlestick_chart_viewer.py --symbol ETH-USD --days 30
    python candlestick_chart_viewer.py --symbol BTC-USD --save btc_chart.png
    python candlestick_chart_viewer.py --symbol PEPE-USD --latest 100 --volume
    python candlestick_chart_viewer.py --list-symbols

Features:
    - Interactive candlestick charts with zoom/pan
    - Optional volume bars
    - Multiple time ranges
    - Save as PNG, JPG, PDF, SVG, HTML
    - Moving averages overlay
    - Professional styling
    - Responsive design

Examples:
    # Basic chart for BTC (last 60 days)
    python candlestick_chart_viewer.py --symbol BTC-USD

    # ETH chart with volume bars for last 30 days
    python candlestick_chart_viewer.py --symbol ETH-USD --days 30 --volume

    # Latest 200 records with moving averages
    python candlestick_chart_viewer.py --symbol BTC-USD --latest 200 --ma

    # Save chart as high-resolution PNG
    python candlestick_chart_viewer.py --symbol BTC-USD --save btc_chart.png --width 1920 --height 1080

    # Export interactive HTML
    python candlestick_chart_viewer.py --symbol ETH-USD --html eth_chart.html

Author: Robinhood Crypto Trading App
Version: 1.0.0
"""
# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring

import sys
import os
import logging
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

from utils import Config
from database import DatabaseManager, DatabaseSession
from database import Historical
from sqlalchemy import desc

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("candlestick_chart")


class CandlestickChartViewer:
    """Creates interactive candlestick charts from database data"""

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

    def get_candlestick_data(
        self,
        symbol: str,
        days: Optional[int] = None,
        latest: Optional[int] = None,
        intervals: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get candlestick data as pandas DataFrame

        Args:
            symbol: Crypto symbol (e.g., BTC-USD)
            days: Number of days back to retrieve
            latest: Number of latest records to retrieve (overrides days)
            intervals: Number of most recent intervals to retrieve (overrides days and latest)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            with DatabaseSession(self.db_manager) as session:
                query = session.query(Historical).filter(
                    Historical.symbol == symbol.upper()
                )

                if intervals:
                    # Get latest N intervals (most recent records)
                    query = query.order_by(desc(Historical.timestamp)).limit(intervals)
                    records = query.all()
                    # Reverse to chronological order
                    records = list(reversed(records))
                elif latest:
                    # Get latest N records
                    query = query.order_by(desc(Historical.timestamp)).limit(latest)
                    records = query.all()
                    # Reverse to chronological order
                    records = list(reversed(records))
                elif days:
                    # Get records from N days ago
                    cutoff_date = datetime.now() - timedelta(days=days)
                    query = query.filter(Historical.timestamp >= cutoff_date)
                    records = query.order_by(Historical.timestamp).all()
                else:
                    # Get all records
                    records = query.order_by(Historical.timestamp).all()

                if not records:
                    return pd.DataFrame()

                # Convert to DataFrame
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

                df = pd.DataFrame(data)
                df.set_index("timestamp", inplace=True)
                return df

        except Exception as e:
            logger.error(f"Error getting data for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_technical_indicators(
        self,
        df: pd.DataFrame,
        sma_period: int = 20,
        bb_period: int = 20,
        bb_std: float = 2.0,
    ) -> pd.DataFrame:
        """Add technical indicators to the DataFrame"""
        if len(df) < max(sma_period, bb_period):
            # Not enough data for indicators
            return df

        df = df.copy()

        # Simple Moving Average (red line)
        df["SMA"] = df["close"].rolling(window=sma_period).mean()

        # Bollinger Bands (blue lines)
        df["BB_Middle"] = df["close"].rolling(window=bb_period).mean()
        df["BB_Std"] = df["close"].rolling(window=bb_period).std()
        df["BB_Upper"] = df["BB_Middle"] + (df["BB_Std"] * bb_std)
        df["BB_Lower"] = df["BB_Middle"] - (df["BB_Std"] * bb_std)

        # Also keep the original moving averages if requested
        if len(df) >= 20:
            df["MA20"] = df["close"].rolling(window=20).mean()
        if len(df) >= 50:
            df["MA50"] = df["close"].rolling(window=50).mean()
        if len(df) >= 200:
            df["MA200"] = df["close"].rolling(window=200).mean()

        return df

    def create_candlestick_chart(
        self,
        symbol: str,
        df: pd.DataFrame,
        show_volume: bool = False,
        show_ma: bool = False,
        show_sma: bool = True,
        show_bollinger: bool = True,
        sma_period: int = 20,
        bb_period: int = 20,
        bb_std: float = 2.0,
        width: int = 1200,
        height: int = 800,
    ) -> go.Figure:
        """
        Create interactive candlestick chart

        Args:
            symbol: Crypto symbol for title
            df: DataFrame with OHLCV data
            show_volume: Whether to show volume bars
            show_ma: Whether to show traditional moving averages (20, 50, 200)
            show_sma: Whether to show Simple Moving Average (red line)
            show_bollinger: Whether to show Bollinger Bands (blue lines)
            sma_period: Period for Simple Moving Average
            bb_period: Period for Bollinger Bands
            bb_std: Standard deviations for Bollinger Bands
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Plotly figure object
        """
        if df.empty:
            # Create empty chart with message
            fig = go.Figure()
            fig.add_annotation(
                text=f"No data available for {symbol}",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=20, color="red"),
            )
            return fig

        # Calculate technical indicators
        df = self.calculate_technical_indicators(df, sma_period, bb_period, bb_std)

        # Create subplots
        if show_volume:
            fig = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.1,
                row_heights=[0.7, 0.3],
                subplot_titles=[f"{symbol} Price with Technical Indicators", "Volume"],
            )
        else:
            fig = make_subplots(
                rows=1,
                cols=1,
                subplot_titles=[f"{symbol} Price with Technical Indicators"],
            )

        # Add candlestick chart
        candlestick = go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_color="#00ff88",  # Green for up
            decreasing_line_color="#ff4444",  # Red for down
            increasing_fillcolor="#00ff88",
            decreasing_fillcolor="#ff4444",
        )

        fig.add_trace(candlestick, row=1, col=1)

        # Add Simple Moving Average (red line)
        if show_sma and "SMA" in df.columns and not df["SMA"].isna().all():
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["SMA"],
                    mode="lines",
                    name=f"SMA({sma_period})",
                    line=dict(color="red", width=2),
                    opacity=0.8,
                ),
                row=1,
                col=1,
            )

        # Add Bollinger Bands (blue lines)
        if (
            show_bollinger
            and "BB_Upper" in df.columns
            and not df["BB_Upper"].isna().all()
        ):
            # Upper band
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["BB_Upper"],
                    mode="lines",
                    name=f"BB Upper({bb_period},{bb_std}σ)",
                    line=dict(color="blue", width=1.5, dash="dot"),
                    opacity=0.7,
                ),
                row=1,
                col=1,
            )

            # Lower band
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["BB_Lower"],
                    mode="lines",
                    name=f"BB Lower({bb_period},{bb_std}σ)",
                    line=dict(color="blue", width=1.5, dash="dot"),
                    opacity=0.7,
                    fill="tonexty",  # Fill between upper and lower bands
                    fillcolor="rgba(0,0,255,0.1)",  # Light blue fill
                ),
                row=1,
                col=1,
            )

            # Middle band (BB basis - usually same as SMA)
            if not show_sma:  # Only show if SMA is not already shown
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df["BB_Middle"],
                        mode="lines",
                        name=f"BB Middle({bb_period})",
                        line=dict(color="darkblue", width=1),
                        opacity=0.5,
                    ),
                    row=1,
                    col=1,
                )

        # Add traditional moving averages if requested
        if show_ma:
            colors = ["orange", "purple", "brown"]
            mas = ["MA20", "MA50", "MA200"]

            for i, ma in enumerate(mas):
                if ma in df.columns and not df[ma].isna().all():
                    fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df[ma],
                            mode="lines",
                            name=ma,
                            line=dict(color=colors[i], width=1.5),
                            opacity=0.7,
                        ),
                        row=1,
                        col=1,
                    )

        # Add volume bars if requested
        if show_volume:
            # Color volume bars based on price direction
            volume_colors = []
            for i in range(len(df)):
                if i == 0:
                    volume_colors.append("#888888")  # Neutral for first bar
                else:
                    if df.iloc[i]["close"] >= df.iloc[i - 1]["close"]:
                        volume_colors.append("#00ff88")  # Green for up
                    else:
                        volume_colors.append("#ff4444")  # Red for down

            volume_bars = go.Bar(
                x=df.index,
                y=df["volume"],
                name="Volume",
                marker_color=volume_colors,
                opacity=0.6,
            )

            fig.add_trace(volume_bars, row=2, col=1)

        # Update layout
        fig.update_layout(
            title={
                "text": f"{symbol} Candlestick Chart with Technical Indicators",
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": 24, "color": "#2c3e50"},
            },
            width=width,
            height=height,
            xaxis_rangeslider_visible=False,  # Remove range slider for cleaner look
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(family="Arial, sans-serif", size=12, color="#2c3e50"),
            hovermode="x unified",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )

        # Update x-axis
        fig.update_xaxes(
            title_text="Date/Time",
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            showspikes=True,
            spikecolor="black",
            spikesnap="cursor",
            spikemode="across",
        )

        # Update y-axis for price
        fig.update_yaxes(
            title_text="Price (USD)",
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            tickformat="$.6f",
            showspikes=True,
            spikecolor="black",
            spikesnap="cursor",
            spikemode="across",
            row=1,
            col=1,
        )

        # Update y-axis for volume
        if show_volume:
            fig.update_yaxes(
                title_text="Volume",
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                row=2,
                col=1,
            )

        return fig

    def save_chart(
        self, fig: go.Figure, filename: str, width: int = 1200, height: int = 800
    ) -> bool:
        """Save chart to file"""
        try:
            # Update figure size for export
            fig.update_layout(width=width, height=height)

            file_ext = filename.lower().split(".")[-1]

            if file_ext == "html":
                fig.write_html(filename)
                logger.info(f"Chart saved as interactive HTML: {filename}")
            elif file_ext in ["png", "jpg", "jpeg", "pdf", "svg"]:
                fig.write_image(filename, engine="kaleido")
                logger.info(f"Chart saved as {file_ext.upper()}: {filename}")
            else:
                logger.error(f"Unsupported file format: {file_ext}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error saving chart: {e}")
            return False

    def show_chart(self, fig: go.Figure) -> None:
        """Display chart in browser"""
        try:
            fig.show()
        except Exception as e:
            logger.error(f"Error displaying chart: {e}")
            print("Could not open browser. Try saving chart to HTML file instead.")

    def list_available_symbols(self) -> None:
        """Print available symbols"""
        symbols = self.get_available_symbols()

        if not symbols:
            print("❌ No symbols found in database")
            return

        print(f"\n📊 Available Symbols ({len(symbols)} total):")
        print("=" * 50)

        # Group by base currency for better display
        symbols_by_base = {}
        for symbol in symbols:
            if "-" in symbol:
                base = symbol.split("-")[0]
                if base not in symbols_by_base:
                    symbols_by_base[base] = []
                symbols_by_base[base].append(symbol)

        for base in sorted(symbols_by_base.keys()):
            print(f"{base}: {', '.join(symbols_by_base[base])}")

        print(f"\nUse any of these symbols with --symbol parameter")

    def cleanup(self):
        """Cleanup database connections"""
        if hasattr(self, "db_manager"):
            self.db_manager.close()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Create interactive candlestick charts for crypto symbols",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic chart with SMA and Bollinger Bands (default)
  python candlestick_chart_viewer.py --symbol BTC-USD --intervals 100

  # Chart showing last 200 intervals with volume
  python candlestick_chart_viewer.py --symbol ETH-USD --intervals 200 --volume

  # Custom technical indicators
  python candlestick_chart_viewer.py --symbol BTC-USD --intervals 150 --sma-period 50 --bb-std 2.5

  # Traditional moving averages instead of SMA/BB
  python candlestick_chart_viewer.py --symbol BTC-USD --no-sma --no-bollinger --ma

  # Save with all indicators
  python candlestick_chart_viewer.py --symbol BTC-USD --intervals 100 --volume --save btc_analysis.png
        """,
    )

    parser.add_argument("--symbol", type=str, help="Crypto symbol (e.g., BTC-USD)")
    parser.add_argument("--days", type=int, help="Number of days to show")
    parser.add_argument("--latest", type=int, help="Show only the latest N records")
    parser.add_argument(
        "--intervals",
        type=int,
        help="Number of most recent intervals to display (overrides days/latest)",
    )
    parser.add_argument("--volume", action="store_true", help="Show volume bars")
    parser.add_argument(
        "--ma",
        action="store_true",
        help="Show traditional moving averages (20, 50, 200)",
    )
    parser.add_argument(
        "--sma",
        action="store_true",
        default=True,
        help="Show Simple Moving Average (red line, default: True)",
    )
    parser.add_argument(
        "--no-sma", dest="sma", action="store_false", help="Hide Simple Moving Average"
    )
    parser.add_argument(
        "--bollinger",
        action="store_true",
        default=True,
        help="Show Bollinger Bands (blue lines, default: True)",
    )
    parser.add_argument(
        "--no-bollinger",
        dest="bollinger",
        action="store_false",
        help="Hide Bollinger Bands",
    )
    parser.add_argument(
        "--sma-period",
        type=int,
        default=20,
        help="Simple Moving Average period (default: 20)",
    )
    parser.add_argument(
        "--bb-period", type=int, default=20, help="Bollinger Bands period (default: 20)"
    )
    parser.add_argument(
        "--bb-std",
        type=float,
        default=2.0,
        help="Bollinger Bands standard deviations (default: 2.0)",
    )
    parser.add_argument(
        "--save", type=str, help="Save chart to file (png, jpg, pdf, svg, html)"
    )
    parser.add_argument("--html", type=str, help="Save as interactive HTML file")
    parser.add_argument("--width", type=int, default=1200, help="Chart width in pixels")
    parser.add_argument(
        "--height", type=int, default=800, help="Chart height in pixels"
    )
    parser.add_argument(
        "--list-symbols", action="store_true", help="List all available symbols"
    )
    parser.add_argument("--config", default="config.json", help="Config file path")

    args = parser.parse_args()

    # Validate arguments
    if not args.list_symbols and not args.symbol:
        parser.error("Must specify --symbol or --list-symbols")

    viewer = None
    try:
        print("📈 Robinhood Crypto Candlestick Chart Viewer")
        print("=" * 50)

        # Initialize viewer
        viewer = CandlestickChartViewer(args.config)

        # Handle list symbols
        if args.list_symbols:
            viewer.list_available_symbols()
            return 0

        # Validate symbol
        symbol = args.symbol.upper()
        available_symbols = viewer.get_available_symbols()

        if symbol not in available_symbols:
            print(f"❌ Symbol '{symbol}' not found in database")
            if available_symbols:
                print("Available symbols:", ", ".join(available_symbols[:10]))
                if len(available_symbols) > 10:
                    print(
                        f"... and {len(available_symbols) - 10} more. Use --list-symbols to see all."
                    )
            return 1

        # Get data
        print(f"📥 Loading data for {symbol}...")
        df = viewer.get_candlestick_data(symbol, args.days, args.latest, args.intervals)

        if df.empty:
            print(f"❌ No data found for {symbol}")
            return 1

        print(f"✅ Loaded {len(df)} records for {symbol}")
        print(
            f"📅 Date range: {df.index[0].strftime('%Y-%m-%d %H:%M')} to {df.index[-1].strftime('%Y-%m-%d %H:%M')}"
        )

        # Create chart
        print("📊 Creating candlestick chart with technical indicators...")
        fig = viewer.create_candlestick_chart(
            symbol,
            df,
            show_volume=args.volume,
            show_ma=args.ma,
            show_sma=args.sma,
            show_bollinger=args.bollinger,
            sma_period=args.sma_period,
            bb_period=args.bb_period,
            bb_std=args.bb_std,
            width=args.width,
            height=args.height,
        )

        # Save chart if requested
        if args.save:
            print(f"💾 Saving chart to {args.save}...")
            if viewer.save_chart(fig, args.save, args.width, args.height):
                print(f"✅ Chart saved successfully!")
            else:
                print(f"❌ Failed to save chart")
                return 1

        if args.html:
            print(f"💾 Saving interactive HTML to {args.html}...")
            if viewer.save_chart(fig, args.html, args.width, args.height):
                print(f"✅ Interactive chart saved successfully!")
            else:
                print(f"❌ Failed to save HTML chart")
                return 1

        # Show chart in browser (unless only saving)
        if not (args.save or args.html):
            print("🌐 Opening chart in browser...")
            viewer.show_chart(fig)
            print("✅ Chart displayed! Check your browser.")
        elif args.save or args.html:
            print("💡 To view chart in browser, run without --save or --html flags")

        return 0

    except ImportError as e:
        if "plotly" in str(e):
            print("❌ Plotly not installed. Run: pip install plotly kaleido")
        elif "pandas" in str(e):
            print("❌ Pandas not installed. Run: pip install pandas")
        else:
            print(f"❌ Missing dependency: {e}")
        return 1

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
