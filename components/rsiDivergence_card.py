# components/rsiDivergence_card.py
from nicegui import ui
import httpx

async def fetch_rsi_divergence_data():
    """Fetch RSI divergence data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/get_ta_data", params={"scanner_type": "rsi_divergence", "limit": 10})
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching RSI divergence data: {e}")
            return []

def rsi_divergence_card():
    """Create a card displaying the top RSI divergence stocks"""
    with ui.card().classes("w-72 p-4 shadow-md"):
        ui.label("RSI Divergence").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest RSI divergence data"""
            ta_data = await fetch_rsi_divergence_data()
            content.clear()
            with content:
                if not ta_data:
                    ui.label("No RSI divergence data available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=4).classes("w-full gap-1"):
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("RSI").classes("text-xs font-semibold text-gray-700")
                        ui.label("Type").classes("text-xs font-semibold text-gray-700")

                        for item in ta_data[:5]:
                            symbol = item.get("symbol", "N/A")
                            price = item.get("price", "N/A")
                            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
                            rsi = item.get("rsi", "N/A")
                            rsi_str = f"{rsi:.2f}" if isinstance(rsi, (int, float)) else "N/A"
                            div_type = item.get("type", "N/A")

                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(rsi_str).classes("text-sm")
                            ui.label(div_type).classes("text-sm")

        ui.timer(0.1, update_card, once=True)
        ui.timer(30.0, update_card)