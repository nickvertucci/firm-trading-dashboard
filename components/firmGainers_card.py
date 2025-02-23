# components/firmGainers_card.py
from nicegui import ui
import httpx

async def fetch_firm_gainers():
    """Fetch firm gainers from the API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/firm_gainers")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching firm gainers data: {e}")
            return {"quotes": []}  # Default to empty quotes list on error

def firm_gainers_card():
    """Create a card displaying the top firm gainers with position change indicators"""
    # Store previous positions in a dictionary (symbol -> position)
    previous_positions = {}

    with ui.card().classes("w-64 p-4 shadow-md"):
        ui.label("Firm Gainers").classes("text-lg font-semibold mb-2")
        content = ui.column().classes("w-full")

        async def update_card():
            """Update the card with the latest firm gainers and position changes"""
            nonlocal previous_positions  # Access the outer scope variable
            gainers_data = await fetch_firm_gainers()
            quotes = gainers_data.get("quotes", [])
            current_positions = {quote.get("symbol", "N/A"): idx for idx, quote in enumerate(quotes[:10])}

            content.clear()
            with content:
                if not quotes:
                    ui.label("No firm gainers available").classes("text-gray-600 text-sm")
                else:
                    with ui.grid(columns=4).classes("w-full gap-1"):  # Increased to 4 columns for arrow
                        # Column headers
                        ui.label("Ticker").classes("text-xs font-semibold text-gray-700")
                        ui.label("Price").classes("text-xs font-semibold text-gray-700")
                        ui.label("% Change").classes("text-xs font-semibold text-gray-700")
                        ui.label("").classes("text-xs font-semibold text-gray-700")  # Empty header for arrow column

                        # Data rows (limit to top 10)
                        for idx, quote in enumerate(quotes[:10]):
                            symbol = quote.get("symbol", "N/A")
                            price = quote.get("regularMarketPrice", "N/A")
                            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "$N/A"
                            percent_change = quote.get("regularMarketChangePercent", "N/A")
                            percent_change_str = f"{percent_change:.2f}%" if isinstance(percent_change, (int, float)) else "N/A"

                            # Determine position change
                            arrow = ""
                            if symbol in previous_positions:
                                prev_pos = previous_positions[symbol]
                                curr_pos = idx
                                if prev_pos > curr_pos:  # Moved up (lower index is better)
                                    arrow = "↑"  # Green up arrow
                                    arrow_color = "text-green-500"
                                elif prev_pos < curr_pos:  # Moved down
                                    arrow = "↓"  # Red down arrow
                                    arrow_color = "text-red-500"
                                else:
                                    arrow = ""  # No change, no arrow

                            # Display row
                            ui.label(symbol).classes("text-sm truncate")
                            ui.label(price_str).classes("text-sm")
                            ui.label(percent_change_str).classes("text-sm")
                            ui.label(arrow).classes(f"text-sm {arrow_color if arrow else ''}")

            # Update previous positions for the next refresh
            previous_positions.update(current_positions)

        # Initial update and periodic refresh
        ui.timer(0.1, update_card, once=True)  # Immediate first load
        ui.timer(30.0, update_card)  # Refresh every 30 seconds
