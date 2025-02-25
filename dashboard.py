# dashboard.py
from nicegui import ui
import httpx
from datetime import datetime
from components.watchlist_card import watchlist_card
from components.mostActivelist_card import most_active_card
from components.smallCapgainers_card import small_cap_gainers_card
from components.firmGainers_card import firm_gainers_card
from components.firmRvolgainers__card import firm_rvol_gainers_card

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

async def fetch_rvol_gainers():
    """Fetch firm rVol gainers from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "http://localhost:8000/api/firm_rvol_gainers",
                params={"size": 10}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching rVol gainers data: {e}")
            return {"quotes": []}

def create_dashboard():
    """Create the full dashboard page with sidebars, rVol table, and watchlist table"""
    # Left Sidebar
    with ui.left_drawer(fixed=False).classes("bg-gray-100 p-4 w-75") as left_sidebar:
        firm_gainers_card()
        firm_rvol_gainers_card()
        small_cap_gainers_card()

    # Right Sidebar
    with ui.right_drawer(fixed=False).classes("bg-gray-100 p-4 w-64") as right_sidebar:
        watchlist = watchlist_card()

    # Main Content Area
    with ui.column().classes("w-full max-w-7xl mx-auto p-4"):
        ui.label("Investment Trading Dashboard").classes("text-2xl font-bold mb-4")
        
        # rVol Gainers Table at the Top
        rvol_table = ui.column().classes("w-full mb-6")
        async def update_rvol_table():
            rvol_data = await fetch_rvol_gainers()
            quotes = rvol_data.get("quotes", [])
            rvol_table.clear()
            with rvol_table:
                if not quotes:
                    ui.label("No rVol gainers available").classes("text-gray-600")
                else:
                    rows = [
                        {
                            "symbol": quote.get("symbol", "N/A"),
                            "name": quote.get("displayName", quote.get("longName", "Unknown")),
                            "rvol": f"{quote.get('rvol', 'N/A'):.2f}%" if isinstance(quote.get("rvol"), (int, float)) else "N/A",
                            "price": f"${quote.get('regularMarketPrice', 'N/A'):.2f}" if isinstance(quote.get("regularMarketPrice"), (int, float)) else "$N/A",
                            "previous price": f"${quote.get('regularMarketPreviousClose', 'N/A'):.2f}" if isinstance(quote.get("regularMarketPreviousClose"), (int, float)) else "$N/A"
                        }
                        for quote in quotes
                    ]
                    ui.table(
                        columns=[
                            {"name": "symbol", "label": "Symbol", "field": "symbol", "align": "left"},
                            {"name": "name", "label": "Name", "field": "name", "align": "left"},
                            {"name": "rvol", "label": "rVol (%)", "field": "rvol", "align": "right"},
                            {"name": "price", "label": "Price", "field": "price", "align": "right"},
                            {"name": "previous price", "label": "Previous Price", "field": "previous price", "align": "right"}
                        ],
                        rows=rows,
                        row_key="symbol"
                    ).classes("w-full").props("dense")
        ui.timer(0.1, update_rvol_table, once=True)
        ui.timer(60.0, update_rvol_table)

        # Watchlist Table Below
        ui.label("Watchlist Tickers").classes("text-2xl font-bold mb-4")
        table = ui.column().classes("w-full")
        async def update_table():
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

    # Sidebar Toggle Buttons
    ui.button("Toggle Left Sidebar", on_click=left_sidebar.toggle).classes("fixed bottom-4 left-4 bg-gray-600 text-white px-4 py-2 rounded")
    ui.button("Toggle Watchlist", on_click=right_sidebar.toggle).classes("fixed bottom-4 right-4 bg-gray-600 text-white px-4 py-2 rounded")

    return update_table

if __name__ in {"__main__", "__mp_main__"}:
    create_dashboard()
    ui.run()