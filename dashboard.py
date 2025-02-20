from nicegui import ui
import httpx
from datetime import datetime
from watchlist import Watchlist

async def fetch_stocks():
    """Fetch stock data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/stocks")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching stock data: {e}")
            return []

def create_dashboard():
    """Create a simple table-based dashboard"""
    ui.label("Investment Trading Dashboard").classes("text-2xl font-bold mb-4")
    
    # Initialize watchlist
    watchlist = Watchlist()
    
    async def update_table():
        """Update the table with latest stock data"""
        stocks_data = await fetch_stocks()
        
        # Clear existing content
        table.clear()
        
        if not stocks_data or not watchlist.watchlist_items:
            with table:
                ui.label("No tickers in watchlist or no data available").classes("text-gray-600")
            return
        
        # Get latest data for each ticker
        latest_by_ticker = {}
        for entry in stocks_data:
            ticker = entry["ticker"]
            timestamp = entry["timestamp"]
            if ticker not in latest_by_ticker or latest_by_ticker[ticker]["timestamp"] < timestamp:
                latest_by_ticker[ticker] = entry
        
        # Get local timezone and latest timestamp
        local_tz = datetime.now().astimezone().tzinfo
        latest_entry = max(stocks_data, key=lambda x: x["timestamp"])
        local_time = datetime.fromisoformat(latest_entry["timestamp"]).astimezone(local_tz).strftime("%H:%M:%S")
        
        # Prepare table rows
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
        
        # Create table
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

    # Create container for table
    table = ui.column().classes("w-full")
    
    # Update every 30 seconds
    ui.timer(30.0, update_table)

# Run the dashboard
if __name__ in {"__main__", "__mp_main__"}:
    create_dashboard()
    ui.run()