# components/emaCrossover_card.py
from nicegui import ui
import httpx

async def fetch_ema_crossover_data():
    """Fetch EMA crossover data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/get_ta_data", params={"scanner_type": "ema_crossover", "limit": 10})
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching EMA crossover data: {e}")
            return []

def ema_crossover_card():
    """Create a card displaying the top EMA crossover stocks"""
    with ui.card().classes("w-72 p-4 shadow-md"):
        ui.label("EMA Crossover").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest EMA crossover data"""
            ta_data = await fetch_ema_crossover_data()
            content.clear()
            with content:
                if not ta_data:
                    ui.label("No EMA crossover data available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=5).classes("w-full gap-1"):
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("% Change").classes("text-xs font-semibold text-gray-700")
                        ui.label("EMA9").classes("text-xs font-semibold text-gray-700")
                        ui.label("EMA26").classes("text-xs font-semibold text-gray-700")

                        for item in ta_data[:5]:
                            symbol = item.get("symbol", "N/A")
                            price = item.get("price", "N/A")
                            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
                            percent_change = item.get("percent_change", "N/A")
                            percent_change_str = f"{percent_change:.2f}%" if isinstance(percent_change, (int, float)) else "N/A"
                            ema_9 = item.get("ema_9", "N/A")
                            ema_9_str = f"{ema_9:.2f}" if isinstance(ema_9, (int, float)) else "N/A"
                            ema_26 = item.get("ema_26", "N/A")
                            ema_26_str = f"{ema_26:.2f}" if isinstance(ema_26, (int, float)) else "N/A"

                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(percent_change_str).classes("text-sm")
                            ui.label(ema_9_str).classes("text-sm")
                            ui.label(ema_26_str).classes("text-sm")

        ui.timer(0.1, update_card, once=True)  # Initial load
        ui.timer(30.0, update_card)  # Refresh every 30 seconds