# components/macdCrossover_card.py
from nicegui import ui
import httpx

async def fetch_macd_crossover_data():
    """Fetch MACD crossover data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/get_ta_data", params={"scanner_type": "macd_crossover", "limit": 10})
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching MACD crossover data: {e}")
            return []

def macd_crossover_card():
    """Create a card displaying the top MACD crossover stocks"""
    with ui.card().classes("w-72 p-4 shadow-md"):
        ui.label("MACD Crossover").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest MACD crossover data"""
            ta_data = await fetch_macd_crossover_data()
            content.clear()
            with content:
                if not ta_data:
                    ui.label("No MACD crossover data available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=5).classes("w-full gap-1"):
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("MACD").classes("text-xs font-semibold text-gray-700")
                        ui.label("Signal").classes("text-xs font-semibold text-gray-700")
                        ui.label("Type").classes("text-xs font-semibold text-gray-700")

                        for item in ta_data[:5]:
                            symbol = item.get("symbol", "N/A")
                            price = item.get("price", "N/A")
                            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
                            macd = item.get("macd", "N/A")
                            macd_str = f"{macd:.2f}" if isinstance(macd, (int, float)) else "N/A"
                            signal = item.get("signal", "N/A")
                            signal_str = f"{signal:.2f}" if isinstance(signal, (int, float)) else "N/A"
                            crossover_type = item.get("type", "N/A")

                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(macd_str).classes("text-sm")
                            ui.label(signal_str).classes("text-sm")
                            ui.label(crossover_type).classes("text-sm")

        ui.timer(0.1, update_card, once=True)
        ui.timer(30.0, update_card)