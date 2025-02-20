from nicegui import ui
import httpx
from datetime import datetime
import pytz
from watchlist import Watchlist

async def fetch_stocks():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("http://localhost:8000/api/stocks")
        return response.json()

def create_dashboard():
    ui.label("Investment Trading Dashboard").classes("text-2xl font-bold mb-4")
    
    # Initialize watchlist
    watchlist = Watchlist()
    
    async def update_table():
        stocks_data = await fetch_stocks()
        if not stocks_data or not watchlist.watchlist_items:
            table.clear()
            with table:
                ui.label("No tickers in watchlist or no data available").classes("text-gray-600")
            return
        
        # Group by timestamp and get latest data for each ticker
        latest_by_ticker = {}
        for entry in stocks_data:
            ticker = entry["ticker"]  # Changed from "symbol"
            timestamp = entry["timestamp"]
            if ticker not in latest_by_ticker or latest_by_ticker[ticker]["timestamp"] < timestamp:
                latest_by_ticker[ticker] = entry
        
        # Convert latest timestamp to local time
        latest_entry = max(stocks_data, key=lambda x: x["timestamp"])
        utc_time = datetime.fromisoformat(latest_entry["timestamp"])  # Handles +00:00
        local_tz = datetime.now().astimezone().tzinfo
        local_time = utc_time.astimezone(local_tz).strftime("%H:%M")
        
        table.clear()
        with table:
            rows = [
                {
                    "ticker": item["ticker"],  # Changed from "symbol"
                    "price": latest_by_ticker.get(item["ticker"], {}).get("close", "N/A"),
                    "timestamp": local_time
                }
                for item in watchlist.watchlist_items
            ]
            ui.table(
                columns=[
                    {"name": "ticker", "label": "Ticker", "field": "ticker"},  # Changed from "symbol"
                    {"name": "price", "label": "Price ($)", "field": "price"},
                    {"name": "timestamp", "label": "Time", "field": "timestamp"}
                ],
                rows=rows
            ).classes("w-full")

    table = ui.column()
    ui.timer(30.0, update_table)

    async def update_chart():
        stocks_data = await fetch_stocks()
        if not stocks_data or not watchlist.watchlist_items:
            chart.options["series"] = []
            chart.options["xAxis"]["data"] = []
            chart.update()
            return
        
        local_tz = datetime.now().astimezone().tzinfo
        default_ticker = watchlist.watchlist_items[0]["ticker"] if watchlist.watchlist_items else None
        
        if default_ticker:
            # Filter data for the default ticker
            ticker_data = [row for row in stocks_data if row["ticker"] == default_ticker]  # Changed from "symbol"
            timestamps = [
                datetime.fromisoformat(row["timestamp"])  # Handles +00:00
                .astimezone(local_tz)
                .strftime("%H:%M")
                for row in ticker_data
            ]
            ohlc_data = [
                [row["open"], row["close"], row["low"], row["high"]]
                for row in ticker_data
            ]
            
            chart.options["title"]["text"] = f"{default_ticker} 1-Minute Candlestick (Today)"
            chart.options["xAxis"]["data"] = timestamps
            chart.options["series"] = [{
                "name": default_ticker,
                "type": "candlestick",
                "data": ohlc_data,
                "itemStyle": {
                    "color": "#00da3c",
                    "color0": "#ec0000",
                    "borderColor": "#00da3c",
                    "borderColor0": "#ec0000"
                },
                "barWidth": 4
            }]
            chart.update()

    chart = ui.echart({
        "title": {"text": "Candlestick Chart"},
        "xAxis": {
            "type": "category",
            "data": [],
            "axisLabel": {"rotate": 45, "interval": 14, "formatter": "{value}"}
        },
        "yAxis": {
            "type": "value",
            "name": "Price ($)",
            "scale": True,
            "min": "dataMin",
            "max": "dataMax"
        },
        "series": [],
        "tooltip": {"trigger": "axis", "formatter": "{b}<br>Open: ${c[0]}<br>Close: ${c[1]}<br>Low: ${c[2]}<br>High: ${c[3]}"},
        "dataZoom": [{"type": "inside"}, {"type": "slider"}]
    }).classes("h-96")
    ui.timer(30.0, update_chart)

# Run the dashboard
ui.run()