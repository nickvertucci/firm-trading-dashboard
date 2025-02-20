# ui.py
from nicegui import ui
import httpx
import pandas as pd

async def fetch_stocks():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/stocks")
        return response.json()

def create_dashboard():
    ui.label("Investment Trading Dashboard").classes("text-2xl font-bold mb-4")

    # Table for latest prices
    async def update_table():
        stocks_data = await fetch_stocks()
        if not stocks_data:
            return
        latest = stocks_data[-1]  # Get the most recent data point
        table.clear()
        with table:
            ui.table(
                columns=[
                    {"name": "symbol", "label": "Symbol", "field": "symbol"},
                    {"name": "price", "label": "Price ($)", "field": "price"},
                    {"name": "timestamp", "label": "Timestamp", "field": "timestamp"}
                ],
                rows=[
                    {"symbol": "AAPL", "price": latest.get("AAPL"), "timestamp": latest["timestamp"]},
                    {"symbol": "GOOGL", "price": latest.get("GOOGL"), "timestamp": latest["timestamp"]},
                    {"symbol": "TSLA", "price": latest.get("TSLA"), "timestamp": latest["timestamp"]}
                ]
            )

    table = ui.column()
    ui.timer(30.0, update_table)

    # Line graph for 1-minute intervals for all three tickers
    async def update_chart():
        stocks_data = await fetch_stocks()
        if not stocks_data:
            return
        # Extract timestamps and prices for each stock
        timestamps = [row["timestamp"] for row in stocks_data]
        aapl_prices = [row["AAPL"] for row in stocks_data if row["AAPL"] is not None]
        googl_prices = [row["GOOGL"] for row in stocks_data if row["GOOGL"] is not None]
        tsla_prices = [row["TSLA"] for row in stocks_data if row["TSLA"] is not None]
        
        # Update chart options
        chart.options["xAxis"]["data"] = timestamps
        chart.options["series"] = [
            {"name": "AAPL", "type": "line", "data": aapl_prices},
            {"name": "GOOGL", "type": "line", "data": googl_prices},
            {"name": "TSLA", "type": "line", "data": tsla_prices}
        ]
        chart.update()

    chart = ui.echart({
        "title": {"text": "1-Minute Stock Prices (Today)"},
        "xAxis": {
            "type": "category",
            "data": [],  # Will be timestamps
            "axisLabel": {
                "rotate": 45,  # Rotate labels for readability
                "formatter": "{value|%H:%M}"  # Show only hour:minute
            }
        },
        "yAxis": {"type": "value", "name": "Price ($)"},
        "series": [
            {"name": "AAPL", "type": "line", "data": []},
            {"name": "GOOGL", "type": "line", "data": []},
            {"name": "TSLA", "type": "line", "data": []}
        ],
        "tooltip": {"trigger": "axis"},  # Show tooltip on hover
        "legend": {"data": ["AAPL", "GOOGL", "TSLA"]}  # Add legend
    }).classes("h-96")  # Increased height for visibility
    ui.timer(30.0, update_chart)