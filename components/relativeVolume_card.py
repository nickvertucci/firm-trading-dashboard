# components/relativeVolume_card.py
from nicegui import ui
import httpx

async def fetch_relative_volume_data():
    """Fetch relative volume data from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "http://localhost:8000/get_ta_data",
                params={"scanner_type": "relative_volume", "limit": 10}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching relative volume data: {e}")
            return []
        except ValueError as e:
            print(f"Error parsing JSON response: {e}")
            return []

def relative_volume_card():
    """Create a card displaying the top relative volume stocks"""
    with ui.card().classes("w-72 p-4 shadow-md"):
        ui.label("Relative Volume").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest relative volume data"""
            ta_data = await fetch_relative_volume_data()
            content.clear()
            with content:
                if not ta_data:
                    ui.label("No relative volume data available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=4).classes("w-full gap-1"):
                        # Headers
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("RVol").classes("text-xs font-semibold text-gray-700")
                        ui.label("Volume").classes("text-xs font-semibold text-gray-700")

                        # Data rows (limited to top 5)
                        for item in ta_data[:5]:
                            # Safely extract and format data with type checking
                            symbol = item.get("symbol", "N/A")
                            price = item.get("price", "N/A")
                            price_str = f"${float(price):.2f}" if isinstance(price, (int, float)) else "$N/A"
                            rvol = item.get("relative_volume", "N/A")
                            rvol_str = f"{float(rvol):.2f}" if isinstance(rvol, (int, float)) else "N/A"
                            volume = item.get("current_volume", "N/A")
                            volume_str = f"{int(volume):,}" if isinstance(volume, (int, float)) else "N/A"

                            # Display row
                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(rvol_str).classes("text-sm")
                            ui.label(volume_str).classes("text-sm")

        # Initial load and periodic refresh
        ui.timer(0.1, update_card, once=True)
        ui.timer(30.0, update_card)