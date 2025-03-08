# components/bollingerSqueeze_card.py
from nicegui import ui
import httpx

async def fetch_bollinger_squeeze_data():
    """Fetch Bollinger Band squeeze data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/get_ta_data", params={"scanner_type": "bollinger_squeeze", "limit": 10})
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching Bollinger squeeze data: {e}")
            return []

def bollinger_squeeze_card():
    """Create a card displaying the top Bollinger Band squeeze stocks"""
    with ui.card().classes("w-72 p-4 shadow-md"):
        ui.label("Bollinger Squeeze").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest Bollinger squeeze data"""
            ta_data = await fetch_bollinger_squeeze_data()
            content.clear()
            with content:
                if not ta_data:
                    ui.label("No Bollinger squeeze data available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=5).classes("w-full gap-1"):
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("Width").classes("text-xs font-semibold text-gray-700")
                        ui.label("Upper").classes("text-xs font-semibold text-gray-700")
                        ui.label("Lower").classes("text-xs font-semibold text-gray-700")

                        for item in ta_data[:5]:
                            symbol = item.get("symbol", "N/A")
                            price = item.get("price", "N/A")
                            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
                            width = item.get("band_width", "N/A")
                            width_str = f"{width:.2f}" if isinstance(width, (int, float)) else "N/A"
                            upper = item.get("upper_band", "N/A")
                            upper_str = f"${upper:.2f}" if isinstance(upper, (int, float)) else "$N/A"
                            lower = item.get("lower_band", "N/A")
                            lower_str = f"${lower:.2f}" if isinstance(lower, (int, float)) else "$N/A"

                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(width_str).classes("text-sm")
                            ui.label(upper_str).classes("text-sm")
                            ui.label(lower_str).classes("text-sm")

        ui.timer(0.1, update_card, once=True)
        ui.timer(30.0, update_card)