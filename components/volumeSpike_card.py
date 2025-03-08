# components/volumeSpike_card.py
from nicegui import ui
import httpx

async def fetch_volume_spike_data():
    """Fetch volume spike data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/get_ta_data", params={"scanner_type": "volume_spike", "limit": 10})
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching volume spike data: {e}")
            return []

def volume_spike_card():
    """Create a card displaying the top volume spike stocks"""
    with ui.card().classes("w-72 p-4 shadow-md"):
        ui.label("Volume Spike").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest volume spike data"""
            ta_data = await fetch_volume_spike_data()
            content.clear()
            with content:
                if not ta_data:
                    ui.label("No volume spike data available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=5).classes("w-full gap-1"):
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("Vol Ratio").classes("text-xs font-semibold text-gray-700")
                        ui.label("Volume").classes("text-xs font-semibold text-gray-700")
                        ui.label("% Change").classes("text-xs font-semibold text-gray-700")

                        for item in ta_data[:5]:
                            symbol = item.get("symbol", "N/A")
                            price = item.get("price", "N/A")
                            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
                            vol_ratio = item.get("volume_ratio", "N/A")
                            vol_ratio_str = f"{vol_ratio:.2f}" if isinstance(vol_ratio, (int, float)) else "N/A"
                            volume = item.get("volume", "N/A")
                            volume_str = f"{volume:,}" if isinstance(volume, int) else "N/A"
                            percent_change = item.get("percent_change", "N/A")
                            percent_change_str = f"{percent_change:.2f}%" if isinstance(percent_change, (int, float)) else "N/A"

                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(vol_ratio_str).classes("text-sm")
                            ui.label(volume_str).classes("text-sm")
                            ui.label(percent_change_str).classes("text-sm")

        ui.timer(0.1, update_card, once=True)
        ui.timer(30.0, update_card)