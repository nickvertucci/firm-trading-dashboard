# dashboard.py
from nicegui import ui
import httpx
import pandas as pd
from datetime import datetime
import pytz

async def fetch_stocks():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get("http://localhost:8000/api/stocks")
        return response.json()

def create_dashboard():
    ui.label("Investment Trading Dashboard").classes("text-2xl font-bold mb-4")

    async def update_table():
        stocks_data = await fetch_stocks()
        if not stocks_data:
            return
        latest = stocks_data[-1]
        utc_time = datetime.strptime(latest["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        local_tz = datetime.now().astimezone().tzinfo
        local_time = utc_time.astimezone(local_tz).strftime("%H:%M")
        table.clear()
        with table:
            ui.table(
                columns=[
                    {"name": "symbol", "label": "Symbol", "field": "symbol"},
                    {"name": "price", "label": "Price ($)", "field": "price"},
                    {"name": "timestamp", "label": "Time", "field": "timestamp"}
                ],
                rows=[
                    {"symbol": "AAPL", "price": latest.get("AAPL", {}).get("close"), "timestamp": local_time},
                    {"symbol": "GOOGL", "price": latest.get("GOOGL", {}).get("close"), "timestamp": local_time},
                    {"symbol": "TSLA", "price": latest.get("TSLA", {}).get("close"), "timestamp": local_time}
                ]
            ).classes("w-full")

    table = ui.column()
    ui.timer(30.0, update_table)

    async def update_chart():
        stocks_data = await fetch_stocks()
        if not stocks_data:
            return
        local_tz = datetime.now().astimezone().tzinfo
        timestamps = [
            datetime.strptime(row["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
            .astimezone(local_tz)
            .strftime("%H:%M")
            for row in stocks_data
        ]
        aapl_ohlc = [
            [row["AAPL"]["open"], row["AAPL"]["close"], row["AAPL"]["low"], row["AAPL"]["high"]]  # Correct order: [O, C, L, H]
            for row in stocks_data if "AAPL" in row and all(k in row["AAPL"] for k in ["open", "high", "low", "close"])
        ]
        
        chart.options["xAxis"]["data"] = timestamps
        chart.options["series"] = [{
            "name": "AAPL",
            "type": "candlestick",
            "data": aapl_ohlc,
            "itemStyle": {
                "color": "#00da3c",  # Green for up (close > open)
                "color0": "#ec0000",  # Red for down (close < open)
                "borderColor": "#00da3c",
                "borderColor0": "#ec0000"
            },
            "barWidth": 4
        }]
        chart.update()

    chart = ui.echart({
        "title": {"text": "AAPL 1-Minute Candlestick (Today)"},
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
        "series": [{
            "name": "AAPL",
            "type": "candlestick",
            "data": [],
            "itemStyle": {
                "color": "#00da3c",
                "color0": "#ec0000",
                "borderColor": "#00da3c",
                "borderColor0": "#ec0000"
            },
            "barWidth": 4
        }],
        "tooltip": {"trigger": "axis", "formatter": "{b}<br>Open: ${c[0]}<br>Close: ${c[1]}<br>Low: ${c[2]}<br>High: ${c[3]}"},  # Updated tooltip
        "dataZoom": [{"type": "inside"}, {"type": "slider"}]
    }).classes("h-96")
    ui.timer(30.0, update_chart)