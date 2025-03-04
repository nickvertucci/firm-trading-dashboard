# components/watchlist_chart_card.py
from nicegui import ui
import httpx
import os
from dotenv import load_dotenv
import asyncio
import math
import logging
import plotly.graph_objects as go

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

class WatchlistCharts:
    def __init__(self):
        self.watchlist_items = []
        self._callbacks = []
        self.load_watchlist()

    def load_watchlist(self):
        """Load watchlist from MongoDB"""
        from pymongo import MongoClient
        mongo_uri = os.getenv("MONGO_URI")
        client = MongoClient(mongo_uri)
        db = client["trading_db"]
        watchlist_collection = db["stock_watchlist"]
        try:
            self.watchlist_items = list(watchlist_collection.find())
            if not self.watchlist_items:
                self.watchlist_items = []
        except Exception as e:
            self.watchlist_items = []

    def add_callback(self, callback):
        self._callbacks.append(callback)

    async def _notify_callbacks(self):
        for callback in self._callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()

async def fetch_ohlcv_intraday_data():
    """Fetch intraday OHLCV data for watchlist tickers from the new API endpoint"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/api/get_stock_ohlcv_intraday")
            response.raise_for_status()
            data = response.json()
            return data
        except httpx.HTTPError as e:
            return []

def watchlist_chart_card(watchlist_instance):
    """Create a card component for OHLCV charts of watchlist tickers, 3 per row using Plotly"""
    charts = WatchlistCharts()

    with ui.card().classes("w-full p-4 shadow-md"):
        ui.label("Watchlist OHLCV Charts").classes("text-lg font-semibold mb-2")
        chart_container = ui.column().classes("w-full")

        async def refresh_charts():
            """Refresh the chart display for all watchlist tickers in a grid layout"""
            try:
                chart_container.clear()
                with chart_container:
                    if not charts.watchlist_items:
                        ui.label("No tickers in watchlist").classes("text-gray-600 text-sm")
                    else:
                        ohlcv_data = await fetch_ohlcv_intraday_data()
                        if not ohlcv_data:
                            ui.label("No intraday OHLCV data available").classes("text-gray-600 text-sm")
                            return

                        # Group data by ticker
                        ticker_data = {}
                        for entry in ohlcv_data:
                            ticker = entry["ticker"]
                            if ticker not in ticker_data:
                                ticker_data[ticker] = []
                            ticker_data[ticker].append(entry)

                        num_tickers = len(charts.watchlist_items)
                        num_rows = math.ceil(num_tickers / 3)

                        for row in range(num_rows):
                            with ui.grid(columns=3).classes("w-full gap-4"):
                                start_idx = row * 3
                                end_idx = min(start_idx + 3, num_tickers)
                                for idx in range(start_idx, end_idx):
                                    ticker = charts.watchlist_items[idx]["ticker"]
                                    entries = ticker_data.get(ticker, [])
                                    if not entries:
                                        with ui.column():
                                            ui.label(f"No data for {ticker} today").classes("text-gray-600 text-sm")
                                        continue

                                    # Prepare full-day data
                                    timestamps = [entry["timestamp"] for entry in entries]
                                    open_data = [entry.get("open", 0) for entry in entries]
                                    high_data = [entry.get("high", 0) for entry in entries]
                                    low_data = [entry.get("low", 0) for entry in entries]
                                    close_data = [entry.get("close", 0) for entry in entries]
                                    volume_data = [entry.get("volume", 0) for entry in entries]

                                    # Create candlestick chart
                                    fig = go.Figure()
                                    fig.add_trace(go.Candlestick(
                                        x=timestamps,
                                        open=open_data,
                                        high=high_data,
                                        low=low_data,
                                        close=close_data,
                                        name="OHLC",
                                        increasing_line_color="green",
                                        decreasing_line_color="red"
                                    ))
                                    fig.update_layout(
                                        height=300,
                                        title=f"{ticker} - Today",
                                        xaxis_title="Time",
                                        yaxis_title="Price (USD)",
                                        xaxis={"tickformat": "%H:%M", "type": "date"},
                                        margin=dict(l=40, r=40, t=40, b=40),
                                        showlegend=False,
                                        template="plotly_white"
                                    )

                                    # Create volume bar chart
                                    volume_fig = go.Figure()
                                    volume_fig.add_trace(go.Bar(
                                        x=timestamps,
                                        y=volume_data,
                                        name="Volume",
                                        marker_color="blue"
                                    ))
                                    volume_fig.update_layout(
                                        height=100,
                                        xaxis_title="Time",
                                        yaxis_title="Volume",
                                        xaxis={"tickformat": "%H:%M", "type": "date"},
                                        margin=dict(l=40, r=40, t=20, b=40),
                                        showlegend=False,
                                        template="plotly_white"
                                    )

                                    with ui.column().classes("w-full"):
                                        ui.plotly(fig).classes("w-full")
                                        ui.plotly(volume_fig).classes("w-full")
            except Exception as e:
                logger.error(f"Error in refresh_charts: {e}")

        # Initial render and bind refresh to watchlist updates
        asyncio.create_task(refresh_charts())
        watchlist_instance.add_callback(lambda: asyncio.create_task(refresh_charts()))

    return charts

# Example usage (for standalone testing)
if __name__ == "__main__":
    from watchlist_card import watchlist_card
    watchlist_instance = watchlist_card()
    watchlist_chart_card(watchlist_instance)
    ui.run()