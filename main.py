# main.py
from nicegui import ui, app as nicegui_app
from fastapi.staticfiles import StaticFiles
from api import app as api_app
from dashboard import create_dashboard
from workers.data_ohlcv_fetcher import DataOHLCVFetcher
from workers.data_info_fetcher import DataInfoFetcher
from workers.data_ta_processor import TAScanner
from components.watchlist_card import Watchlist
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingDashboard")

# Mount the API routes at /api
nicegui_app.mount("/api", api_app)

# Mount static files at /static
nicegui_app.mount("/static", StaticFiles(directory="static", html=True), name="static")

def create_header():
    with ui.header().classes("bg-gray-800 text-white p-4 flex justify-between items-center"):
        with ui.row().classes("items-center gap-2"):
            ui.label("Trading Dashboard").classes("text-xl font-bold")
            with ui.row().classes("items-center gap-1"):
                ui.label("OHLCV:").classes("text-xs")
                price_chip = ui.chip("", icon="sync", color="green-500").classes("text-xs px-2 py-1")
                price_chip.bind_text_from(data_fetcher.stock_data_worker, "running", lambda r: "Running" if r else "Stopped")
                def update_price_chip():
                    price_chip.props(f"icon={'sync' if data_fetcher.stock_data_worker.running else 'stop'}")
                    price_chip.style(f"background-color: {'#16a34a' if data_fetcher.stock_data_worker.running else '#dc2626'}; color: white;")
                ui.timer(1.0, update_price_chip, once=False)
            with ui.row().classes("items-center gap-1"):
                ui.label("Info:").classes("text-xs")
                info_chip = ui.chip("", icon="sync", color="green-500").classes("text-xs px-2 py-1")
                info_chip.bind_text_from(info_fetcher.stock_info_worker, "running", lambda r: "Running" if r else "Stopped")
                def update_info_chip():
                    info_chip.props(f"icon={'sync' if info_fetcher.stock_info_worker.running else 'stop'}")
                    info_chip.style(f"background-color: {'#16a34a' if info_fetcher.stock_info_worker.running else '#dc2626'}; color: white;")
                ui.timer(1.0, update_info_chip, once=False)
            with ui.row().classes("items-center gap-1"):
                ui.label("TA:").classes("text-xs")
                ta_chip = ui.chip("", icon="sync", color="green-500").classes("text-xs px-2 py-1")
                ta_chip.bind_text_from(ta_scanner, "running", lambda r: "Running" if r else "Stopped")
                def update_ta_chip():
                    ta_chip.props(f"icon={'sync' if ta_scanner.running else 'stop'}")
                    ta_chip.style(f"background-color: {'#16a34a' if ta_scanner.running else '#dc2626'}; color: white;")
                ui.timer(1.0, update_ta_chip, once=False)
        
        with ui.row().classes("gap-4"):
            ui.button("Home", on_click=lambda: ui.navigate.to("/")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("About", on_click=lambda: ui.notify("About page coming soon!")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")

@ui.page("/")
def home_page():
    create_header()
    with ui.column().classes("w-full max-w-2xl mx-auto p-4"):
        ui.label("Welcome to Your Trading Dashboard").classes("text-3xl font-bold text-center mb-6")
        with ui.card().classes("w-full"):
            ui.label("Navigate:").classes("text-lg font-semibold mb-2")
            with ui.column().classes("w-full"):
                ui.button("Go to Dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes("w-full mb-2")
                ui.button("About", on_click=lambda: ui.notify("About page coming soon!")).classes("w-full mb-2")
        ui.label("Powered by NiceGUI & xAI").classes("text-sm text-gray-500 mt-4 text-center")

@ui.page("/dashboard")
async def dashboard_page():
    logger.info("Entering dashboard_page")
    create_header()
    create_dashboard()
    logger.info("Dashboard page fully created")

# Initialize workers
data_fetcher = DataOHLCVFetcher(Watchlist)
info_fetcher = DataInfoFetcher(Watchlist)
ta_scanner = TAScanner()

price_task = None
info_task = None
ta_task = None

async def start_workers():
    global price_task, info_task, ta_task
    try:
        price_task = asyncio.create_task(data_fetcher.start())
        logger.info("Scheduled OHLCV worker")
        info_task = asyncio.create_task(info_fetcher.start())
        logger.info("Scheduled Info worker")
        ta_task = asyncio.create_task(ta_scanner.run(scan_interval=300))
        logger.info("Scheduled TA worker")
    except Exception as e:
        logger.error(f"Error scheduling workers: {e}")

@nicegui_app.on_startup
async def startup():
    logger.info("Starting API and workers")
    # No need to await API mount explicitly; it's synchronous
    asyncio.create_task(start_workers())
    logger.info("Startup completed, API mounted and workers scheduled")

@nicegui_app.on_shutdown
async def shutdown():
    global price_task, info_task, ta_task
    try:
        if price_task:
            price_task.cancel()
        if info_task:
            info_task.cancel()
        if ta_task:
            ta_task.cancel()
        await asyncio.gather(price_task, info_task, ta_task, return_exceptions=True)
        logger.info("Shut down all workers")
    except Exception as e:
        logger.error(f"Error cancelling worker tasks: {e}")

if __name__ in {"__main__", "__mp_main__"}:
    logger.info("Starting NiceGUI app")
    ui.run(host="0.0.0.0", port=8000, reload=True, title="Firm Trading Dashboard", favicon="static/favicon.ico")