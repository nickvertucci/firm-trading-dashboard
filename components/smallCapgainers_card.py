# components/smallCapgainers_card.py
from nicegui import ui
import httpx

async def fetch_small_cap_gainers():
    """Fetch small-cap gainers from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/small_cap_gainers")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching small-cap gainers data: {e}")
            return {"quotes": []}  # Default to empty quotes list on error

def small_cap_gainers_card():
    """Create a card displaying the top small-cap gainers in a table layout"""
    with ui.card().classes("w-64 p-4 shadow-md"):
        ui.label("Small-Cap Gainers").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest small-cap gainers"""
            gainers_data = await fetch_small_cap_gainers()
            quotes = gainers_data.get("quotes", [])
            content.clear()
            with content:
                if not quotes:
                    ui.label("No small-cap gainers available").classes("text-gray-600 text-sm")
                else:
                    # Create a grid for table layout
                    with ui.grid(columns=3).classes("w-full gap-1"):
                        # Column headers
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Name").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        
                        # Data rows (limit to top 10)
                        for quote in quotes[:10]:
                            symbol = quote.get("symbol", "N/A")
                            name = quote.get("displayName", quote.get("longName", "Unknown"))
                            price = quote.get("regularMarketPrice", "N/A")
                            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
                            
                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(name).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")

        # Initial update and periodic refresh
        ui.timer(0.1, update_card, once=True)  # Immediate first load
        ui.timer(30.0, update_card)  # Refresh every minute (adjust as needed)