# components/momentumBreakout_card.py
from nicegui import ui
import httpx

async def fetch_momentum_breakout_data():
    """Fetch momentum breakout data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/get_ta_data", params={"scanner_type": "momentum_breakout", "limit": 10})
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching momentum breakout data: {e}")
            return []

def momentum_breakout_card():
    """Create a card displaying the top momentum breakout stocks"""
    with ui.card().classes("w-72 p-4 shadow-md"):
        ui.label("Momentum Breakout").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest momentum breakout data"""
            ta_data = await fetch_momentum_breakout_data()
            content.clear()
            with content:
                if not ta_data:
                    ui.label("No momentum breakout data available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=4).classes("w-full gap-1"):
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("Volume").classes("text-xs font-semibold text-gray-700")
                        ui.label("High").classes("text-xs font-semibold text-gray-700")

                        for item in ta_data[:5]:
                            symbol = item.get("symbol", "N/A")
                            price = item.get("price", "N/A")
                            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
                            volume = item.get("volume", "N/A")
                            volume_str = f"{volume:,}" if isinstance(volume, int) else "N/A"
                            high = item.get("highest_high", "N/A")
                            high_str = f"${high:.2f}" if isinstance(high, (int, float)) else "$N/A"

                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(volume_str).classes("text-sm")
                            ui.label(high_str).classes("text-sm")

        ui.timer(0.1, update_card, once=True)
        ui.timer(30.0, update_card)