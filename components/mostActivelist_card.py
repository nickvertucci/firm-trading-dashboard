# components/mostActivelist.py
from nicegui import ui
import httpx

async def fetch_most_actives():
    """Fetch most active stocks from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/most_actives")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching most actives data: {e}")
            return {"quotes": []}

def most_active_card():
    """Create a card displaying the most active stocks"""
    with ui.card().classes("w-64 p-4 shadow-md"):
        ui.label("Most Active Stocks").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest most active stocks"""
            most_actives_data = await fetch_most_actives()
            quotes = most_actives_data.get("quotes", [])
            content.clear()
            with content:
                if not quotes:
                    ui.label("No active stocks available").classes("text-gray-600 text-sm")
                else:
                    for quote in quotes[:10]:  # Limit to top 10
                        ui.label(
                            f"${quote['symbol']} - ${quote['regularMarketPrice']:.2f}"
                        ).classes("text-sm truncate")

        # Initial update and periodic refresh
        ui.timer(0.1, update_card, once=True)  # Immediate first load
        ui.timer(30.0, update_card)  # Refresh every minute (adjust as needed)