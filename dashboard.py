# dashboard.py
from nicegui import ui
import httpx
from datetime import datetime
from watchlist import Watchlist

async def fetch_stocks():
    """Fetch stock OHLCV data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/get_stock_ohlcv_data")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching stock data: {e}")
            return []

async def fetch_most_actives():
    """Fetch most active stocks from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/most_actives")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching most actives data: {e}")
            return {"quotes": []}

async def update_most_actives_sidebar(sidebar_content):
    """Update the left sidebar with most active stocks"""
    most_actives_data = await fetch_most_actives()
    quotes = most_actives_data.get("quotes", [])
    sidebar_content.clear()
    with sidebar_content:
        if not quotes:
            ui.label("No active stocks available").classes("text-gray-600")
        else:
            ui.label("Most Active Stocks").classes("text-lg font-semibold mb-2")
            for quote in quotes[:10]:  # Limit to top 10
                ui.label(
                    f"{quote['symbol']} - {quote.get('displayName', quote['longName'])} ${quote['regularMarketPrice']:.2f}"
                ).classes("text-sm")

def create_dashboard(watchlist):
    """Create a simple table-based dashboard that reacts to watchlist changes"""
    ui.label("Investment Trading Dashboard").classes("text-2xl font-bold mb-4")
    
    table = ui.column().classes("w-full")
    
    async def update_table():
        """Update the table with the latest stock data"""
        stocks_data = await fetch_stocks()
        if not stocks_data or not watchlist.watchlist_items:
            table.clear()
            with table:
                ui.label("No tickers in watchlist or no data available").classes("text-gray-600")
            return
        
        latest_by_ticker = {}
        for entry in stocks_data:
            ticker = entry["ticker"]
            timestamp = entry["timestamp"]
            if ticker not in latest_by_ticker or latest_by_ticker[ticker]["timestamp"] < timestamp:
                latest_by_ticker[ticker] = entry
        
        local_tz = datetime.now().astimezone().tzinfo
        latest_entry = max(stocks_data, key=lambda x: x["timestamp"])
        local_time = datetime.fromisoformat(latest_entry["timestamp"]).astimezone(local_tz).strftime("%H:%M:%S")
        
        table.clear()
        rows = []
        for item in watchlist.watchlist_items:
            ticker = item["ticker"]
            price_data = latest_by_ticker.get(ticker, {})
            price = price_data.get("close", "N/A")
            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
            rows.append({
                "ticker": ticker,
                "price": price_str,
                "timestamp": local_time
            })
        
        with table:
            ui.table(
                columns=[
                    {"name": "ticker", "label": "Ticker", "field": "ticker", "align": "left"},
                    {"name": "price", "label": "Price", "field": "price", "align": "right"},
                    {"name": "timestamp", "label": "Last Updated", "field": "timestamp", "align": "center"}
                ],
                rows=rows,
                row_key="ticker"
            ).classes("w-full").props("dense")

    watchlist.add_callback(update_table)
    ui.timer(0.1, update_table, once=True)
    
    return update_table

if __name__ in {"__main__", "__mp_main__"}:
    watchlist = Watchlist()
    create_dashboard(watchlist)
    ui.run()