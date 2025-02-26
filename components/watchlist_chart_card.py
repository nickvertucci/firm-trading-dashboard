# components/watchlist_chart_card.py
from nicegui import ui
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import pymongo
from datetime import datetime, date
import asyncio
import math

# Load environment variables
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
watchlist_collection = db["stock_watchlist"]
stock_prices_collection = db["stock_prices"]

class WatchlistCharts:
    def __init__(self):
        self.watchlist_items = []
        self._callbacks = []  # List to store update callbacks
        self.load_watchlist()

    def load_watchlist(self):
        """Load watchlist from MongoDB"""
        self.watchlist_items = list(watchlist_collection.find())
        if not self.watchlist_items:
            self.watchlist_items = []

    def add_callback(self, callback):
        """Register a callback to be called when the watchlist changes."""
        self._callbacks.append(callback)

    async def _notify_callbacks(self):
        """Notify all registered callbacks of a change, awaiting async ones."""
        for callback in self._callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()

def watchlist_chart_card(watchlist_instance):
    """Create a card component for OHLCV charts of watchlist tickers, 3 per row"""
    charts = WatchlistCharts()

    with ui.card().classes("w-full p-4 shadow-md"):
        ui.label("Watchlist OHLCV Charts").classes("text-lg font-semibold mb-2")
        chart_container = ui.column().classes("w-full")

        def fetch_ohlcv_data(ticker):
            """Fetch OHLCV data for the current day from stock_prices collection"""
            today = date.today()
            start_of_day = datetime(today.year, today.month, today.day)
            data = list(stock_prices_collection.find({
                "ticker": ticker.upper(),
                "timestamp": {"$gte": start_of_day}
            }).sort("timestamp", 1))
            return data

        def refresh_charts():
            """Refresh the chart display for all watchlist tickers in a grid layout"""
            chart_container.clear()
            with chart_container:
                if not charts.watchlist_items:
                    ui.label("No tickers in watchlist").classes("text-gray-600 text-sm")
                else:
                    # Calculate number of rows needed (3 charts per row)
                    num_tickers = len(charts.watchlist_items)
                    num_rows = math.ceil(num_tickers / 3)  # Round up to ensure all tickers fit

                    # Create a grid with 3 columns
                    for row in range(num_rows):
                        with ui.grid(columns=3).classes("w-full gap-4"):
                            start_idx = row * 3
                            end_idx = min(start_idx + 3, num_tickers)  # Don't exceed ticker count
                            for idx in range(start_idx, end_idx):
                                ticker = charts.watchlist_items[idx]["ticker"]
                                ohlcv_data = fetch_ohlcv_data(ticker)
                                if not ohlcv_data:
                                    with ui.column():
                                        ui.label(f"No data for {ticker} today").classes("text-gray-600 text-sm")
                                    continue

                                # Prepare data for candlestick chart
                                series_data = [{
                                    "x": entry["timestamp"].isoformat(),
                                    "y": [
                                        entry.get("open", 0),
                                        entry.get("high", 0),
                                        entry.get("low", 0),
                                        entry.get("close", 0)
                                    ]
                                } for entry in ohlcv_data]

                                volume_data = [{
                                    "x": entry["timestamp"].isoformat(),
                                    "y": entry.get("volume", 0)
                                } for entry in ohlcv_data]

                                # Create a combined OHLC + Volume chart
                                with ui.column().classes("w-full"):
                                    ui.label(f"{ticker} - Today").classes("text-md font-medium")
                                    ui.chart({
                                        "chart": {
                                            "type": "candlestick",
                                            "height": 300,
                                            "toolbar": {"show": True}
                                        },
                                        "series": [
                                            {"name": "OHLC", "data": series_data}
                                        ],
                                        "xaxis": {
                                            "type": "datetime",
                                            "labels": {"format": "HH:mm"}
                                        },
                                        "yaxis": {
                                            "title": {"text": "Price (USD)"}
                                        }
                                    }).classes("w-full")

                                    ui.chart({
                                        "chart": {
                                            "type": "bar",
                                            "height": 100,
                                            "toolbar": {"show": False}
                                        },
                                        "series": [
                                            {"name": "Volume", "data": volume_data}
                                        ],
                                        "xaxis": {
                                            "type": "datetime",
                                            "labels": {"format": "HH:mm"}
                                        },
                                        "yaxis": {
                                            "title": {"text": "Volume"}
                                        }
                                    }).classes("w-full")

        # Initial render and bind refresh to watchlist updates
        refresh_charts()
        watchlist_instance.add_callback(refresh_charts)  # Sync callback to refresh charts when watchlist changes

    return charts  # Return the WatchlistCharts instance for potential external use

# Example usage (for standalone testing)
if __name__ == "__main__":
    from watchlist_card import watchlist_card  # Import to get a Watchlist instance
    watchlist_instance = watchlist_card()
    watchlist_chart_card(watchlist_instance)
    ui.run()