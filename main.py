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
from multiprocessing import Process
import sys

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TradingDashboard")

nicegui_app.mount("/api", api_app)
nicegui_app.mount("/static", StaticFiles(directory="static", html=True), name="static")

def create_header():
    with ui.header().classes("bg-gray-800 text-white p-4 flex justify-between items-center"):
        with ui.row().classes("items-center gap-2"):
            ui.label("Trading Dashboard").classes("text-xl font-bold")
        with ui.row().classes("gap-4"):
            ui.button("Home", on_click=lambda: ui.navigate.to("/")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("About", on_click=lambda: ui.notify("About page coming soon!")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")

@ui.page("/")
def home_page():
    logger.debug("Rendering home page")
    create_header()
    with ui.column().classes("w-full max-w-2xl mx-auto p-4"):
        ui.label("Welcome to Your Trading Dashboard").classes("text-3xl font-bold text-center mb-6")
        with ui.card().classes("w-full"):
            ui.label("Navigate:").classes("text-lg font-semibold mb-2")
            with ui.column().classes("w-full"):
                ui.button("Go to Dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes("w-full mb-2")
                ui.button("About", on_click=lambda: ui.notify("About page coming soon!")).classes("w-full mb-2")
        ui.label("Powered by NiceGUI & xAI").classes("text-sm text-gray-500 mt-4 text-center")
    logger.debug("Home page rendered")

@ui.page("/dashboard")
async def dashboard_page():
    logger.debug("Entering dashboard_page")
    create_header()
    create_dashboard()
    logger.debug("Dashboard page fully created")

# Worker process function
def run_workers():
    logging.basicConfig(level=logging.DEBUG)
    worker_logger = logging.getLogger("WorkerProcess")
    worker_logger.info("Starting worker process")
    
    data_fetcher = DataOHLCVFetcher(Watchlist)
    info_fetcher = DataInfoFetcher(Watchlist)
    ta_scanner = TAScanner()

    async def worker_loop():
        try:
            await asyncio.gather(
                data_fetcher.start(),
                info_fetcher.start(),
                ta_scanner.run(scan_interval=300)
            )
        except Exception as e:
            worker_logger.error(f"Worker loop error: {e}")

    asyncio.run(worker_loop())

worker_process = None

@nicegui_app.on_startup
async def startup():
    global worker_process
    logger.debug("Starting API and app")
    worker_process = Process(target=run_workers, daemon=True)
    worker_process.start()
    logger.debug(f"Started worker process with PID {worker_process.pid}")

@nicegui_app.on_shutdown
async def shutdown():
    global worker_process
    if worker_process:
        worker_process.terminate()
        worker_process.join()
        logger.info("Worker process terminated")
    logger.info("Shutting down app")

if __name__ in {"__main__", "__mp_main__"}:
    logger.info("Starting NiceGUI app")
    ui.run(host="0.0.0.0", port=8000, reload=True, title="Firm Trading Dashboard", favicon="static/favicon.ico")