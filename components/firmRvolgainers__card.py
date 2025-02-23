# components/firm_rvol_gainers_card.py
from nicegui import ui
import httpx

async def fetch_firm_rvol_gainers(offset=0, size=10):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "http://localhost:8000/api/firm_rvol_gainers",
                params={"fields": "displayName,symbol,rvol", "offset": offset, "size": size}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching firm rVol gainers data: {e}")
            return {"quotes": []}

def firm_rvol_gainers_card():
    with ui.card().classes("w-64 p-4 shadow-md"):
        ui.label("Firm rVol Gainers").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            gainers_data = await fetch_firm_rvol_gainers()
            quotes = gainers_data.get("quotes", [])
            content.clear()
            with content:
                if not quotes:
                    ui.label("No firm rVol gainers available").classes("text-gray-600 text-sm")
                else:
                    for quote in quotes:
                        symbol = quote.get("symbol", "N/A")
                        name = quote.get("displayName", "Unknown")
                        rvol = quote.get("rvol", "N/A")
                        rvol_str = f"{rvol:.2f}%" if isinstance(rvol, (int, float)) else "N/A"
                        ui.label(f"{symbol} - {name} ({rvol_str})").classes("text-sm truncate")

        ui.timer(0.1, update_card, once=True)
        ui.timer(30.0, update_card)