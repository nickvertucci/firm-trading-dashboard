# dashboard.py
from nicegui import ui
import httpx
from datetime import datetime, date
import pytz
from components.watchlist_card import watchlist_card
from components.watchlist_chart_card import watchlist_chart_card
from components.mostActivelist_card import most_active_card
from components.smallCapgainers_card import small_cap_gainers_card
from components.firmGainers_card import firm_gainers_card
from components.firmRvolgainers__card import firm_rvol_gainers_card
from components.emaCrossover_card import ema_crossover_card
from components.relativeVolume_card import relative_volume_card
from components.momentumBreakout_card import momentum_breakout_card
from components.rsiDivergence_card import rsi_divergence_card
from components.volumeSpike_card import volume_spike_card
from components.macdCrossover_card import macd_crossover_card
from components.bollingerSqueeze_card import bollinger_squeeze_card
import logging
import asyncio

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def fetch_rvol_gainers():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                "http://localhost:8000/api/firm_rvol_gainers",
                params={"size": 10}
            )
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Fetched rVol gainers data: {len(data.get('quotes', []))} quotes")
            return data
        except httpx.HTTPError as e:
            logger.error(f"Error fetching rVol gainers data: {e}")
            return {"quotes": []}

def create_dashboard():
    logger.info("Starting create_dashboard")
    # Left Sidebar
    with ui.left_drawer(fixed=False).classes("bg-gray-100 p-4 w-75") as left_sidebar:
        firm_gainers_card()
        firm_rvol_gainers_card()
        small_cap_gainers_card()
    logger.info("Left sidebar created")

    # Right Sidebar
    with ui.right_drawer(fixed=False).classes("bg-gray-100 p-4 w-64") as right_sidebar:
        watchlist = watchlist_card()
    logger.info("Right sidebar created")

    # Main Content Area
    with ui.column().classes("w-full max-w-7xl mx-auto p-4"):
        ui.label("Investment Trading Dashboard").classes("text-2xl font-bold mb-4")
        logger.info("Dashboard title added")
        
        # rVol Gainers Table
        rvol_table = ui.column().classes("w-full mb-6")
        with rvol_table:
            ui.label("Loading rVol gainers...").classes("text-gray-600")
        async def update_rvol_table():
            try:
                logger.info("Fetching rVol gainers data")
                rvol_data = await fetch_rvol_gainers()
                quotes = rvol_data.get("quotes", [])
                rvol_table.clear()
                with rvol_table:
                    if not quotes:
                        ui.label("No rVol gainers available").classes("text-gray-600")
                    else:
                        rows = [
                            {
                                "symbol": quote.get("symbol", "N/A"),
                                "name": quote.get("displayName", quote.get("longName", "Unknown")),
                                "rvol": f"{quote.get('rvol', 'N/A'):.2f}%" if isinstance(quote.get("rvol"), (int, float)) else "N/A",
                                "price": f"${quote.get('regularMarketPrice', 'N/A'):.2f}" if isinstance(quote.get("regularMarketPrice"), (int, float)) else "$N/A",
                                "previous price": f"${quote.get('regularMarketPreviousClose', 'N/A'):.2f}" if isinstance(quote.get("regularMarketPreviousClose"), (int, float)) else "$N/A"
                            }
                            for quote in quotes
                        ]
                        ui.table(
                            columns=[
                                {"name": "symbol", "label": "Symbol", "field": "symbol", "align": "left"},
                                {"name": "name", "label": "Name", "field": "name", "align": "left"},
                                {"name": "rvol", "label": "rVol (%)", "field": "rvol", "align": "right"},
                                {"name": "price", "label": "Price", "field": "price", "align": "right"},
                                {"name": "previous price", "label": "Previous Price", "field": "previous price", "align": "right"}
                            ],
                            rows=rows,
                            row_key="symbol"
                        ).classes("w-full").props("dense")
                logger.info("rVol table updated")
            except Exception as e:
                logger.error(f"Error updating rVol table: {e}")
                rvol_table.clear()
                with rvol_table:
                    ui.label("Error loading rVol gainers").classes("text-red-600")
        ui.timer(5.0, update_rvol_table, once=True)  # Increased delay
        ui.timer(60.0, update_rvol_table)
        logger.info("rVol table added")

        # Technical Analysis Cards Section
        ui.label("Technical Analysis Scanners").classes("text-2xl font-bold mb-4")
        with ui.row().classes("w-full flex-wrap gap-4"):
            ema_crossover_card()
            relative_volume_card()
            momentum_breakout_card()
            rsi_divergence_card()
            volume_spike_card()
            macd_crossover_card()
            bollinger_squeeze_card()
        logger.info("TA cards added")

    ui.button("Toggle Left Sidebar", on_click=left_sidebar.toggle).classes("fixed bottom-4 left-4 bg-gray-600 text-white px-4 py-2 rounded")
    ui.button("Toggle Watchlist", on_click=right_sidebar.toggle).classes("fixed bottom-4 right-4 bg-gray-600 text-white px-4 py-2 rounded")
    logger.info("Sidebar buttons added")
