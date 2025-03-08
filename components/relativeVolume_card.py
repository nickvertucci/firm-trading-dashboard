# components/relativeVolume_card.py
from nicegui import ui
import httpx

async def fetch_relative_volume_data():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                "http://localhost:8000/api/get_ta_data",
                params={"scanner_type": "relative_volume", "limit": 10}
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching relative volume data: {e}")
            return []

def relative_volume_card():
    with ui.card().classes("w-72 p-4 shadow-md"):
        ui.label("Relative Volume").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")
        with content:
            ui.label("Loading...").classes("text-gray-600 text-sm")

        async def update_card():
            ta_data = await fetch_relative_volume_data()
            content.clear()
            with content:
                if not ta_data:
                    ui.label("No relative volume data available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=4).classes("w-full gap-1"):
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("RVol").classes("text-xs font-semibold text-gray-700")
                        ui.label("Volume").classes("text-xs font-semibold text-gray-700")
                        for item in ta_data[:5]:
                            symbol = item.get("symbol", "N/A")
                            price = item.get("price", "N/A")
                            price_str = f"${float(price):.2f}" if isinstance(price, (int, float)) else "$N/A"
                            rvol = item.get("relative_volume", "N/A")
                            rvol_str = f"{float(rvol):.2f}" if isinstance(rvol, (int, float)) else "N/A"
                            volume = item.get("current_volume", "N/A")
                            volume_str = f"{int(volume):,}" if isinstance(volume, (int, float)) else "N/A"
                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(rvol_str).classes("text-sm")
                            ui.label(volume_str).classes("text-sm")
        ui.timer(5.0, update_card, once=True)  # Increased delay
        ui.timer(30.0, update_card)