# main.py
from nicegui import ui, app as nicegui_app
from api import app as api_app
from dashboard import create_dashboard, update_most_actives_sidebar
from watchlist import Watchlist
from workers import DataOHLCVFetcher, DataInfoFetcher
import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingDashboard")

# Mount the API routes at /api
nicegui_app.mount("/api", api_app)

# Shared header navigation with worker status chips
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
                update_price_chip()
                ui.timer(1.0, update_price_chip)
                price_chip.on("click", lambda: ui.notify(f"OHLCV Worker: {'Running' if data_fetcher.stock_data_worker.running else 'Stopped'}"))

            with ui.row().classes("items-center gap-1"):
                ui.label("Info:").classes("text-xs")
                info_chip = ui.chip("", icon="sync", color="green-500").classes("text-xs px-2 py-1")
                info_chip.bind_text_from(info_fetcher.stock_info_worker, "running", lambda r: "Running" if r else "Stopped")
                def update_info_chip():
                    info_chip.props(f"icon={'sync' if info_fetcher.stock_info_worker.running else 'stop'}")
                    info_chip.style(f"background-color: {'#16a34a' if info_fetcher.stock_info_worker.running else '#dc2626'}; color: white;")
                update_info_chip()
                ui.timer(1.0, update_info_chip)
                info_chip.on("click", lambda: ui.notify(f"Info Worker: {'Running' if info_fetcher.stock_info_worker.running else 'Stopped'}"))
        
        with ui.row().classes("gap-4"):
            ui.button("Home", on_click=lambda: ui.navigate.to("/")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("About", on_click=lambda: ui.notify("About page coming soon!")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("Settings", on_click=lambda: ui.notify("Settings page coming soon!")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")

# Homepage at /
@ui.page("/")
def home_page():
    logger.info("Rendering home page")
    create_header()
    with ui.column().classes("w-full max-w-2xl mx-auto p-4"):
        ui.label("Welcome to Your Trading Dashboard").classes("text-3xl font-bold text-center mb-6")
        with ui.card().classes("w-full"):
            ui.label("Navigate:").classes("text-lg font-semibold mb-2")
            with ui.column().classes("w-full"):
                ui.button("Go to Dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes("w-full mb-2")
                ui.button("About", on_click=lambda: ui.notify("About page coming soon!")).classes("w-full mb-2")
                ui.button("Settings", on_click=lambda: ui.notify("Settings page coming soon!")).classes("w-full")
        ui.label("Powered by NiceGUI & xAI").classes("text-sm text-gray-500 mt-4 text-center")

# Dashboard at /dashboard
@ui.page("/dashboard")
async def dashboard_page():
    logger.info("Rendering dashboard page")
    update_table_callback = None  # Define outside try block
    
    try:
        create_header()
        
        # Left sidebar for most actives
        with ui.left_drawer(fixed=False).classes("bg-gray-100 p-4 w-1/4") as left_sidebar:
            left_sidebar_content = ui.column().classes("w-full")
            await update_most_actives_sidebar(left_sidebar_content)  # Initial update
            ui.timer(60.0, lambda: update_most_actives_sidebar(left_sidebar_content))

        # Main content area with table
        with ui.card().classes("w-full max-w-4xl mx-auto p-4"):
            update_table_callback = create_dashboard(shared_watchlist)

        # Right sidebar for watchlist
        with ui.right_drawer(fixed=True).classes("bg-gray-100 p-4 w-1/4") as right_sidebar:
            right_sidebar_content = ui.column()
            async def update_right_sidebar():
                right_sidebar_content.clear()
                with right_sidebar_content:
                    shared_watchlist.build()
            shared_watchlist.add_callback(update_right_sidebar)
            await update_right_sidebar()
            ui.button("Toggle Watchlist", on_click=right_sidebar.toggle).classes("mt-4")

        # Toggle buttons for both sidebars
        ui.button("Toggle Most Actives", on_click=left_sidebar.toggle).classes("fixed bottom-4 left-4 bg-gray-600 text-white px-4 py-2 rounded")
        ui.button("Toggle Watchlist", on_click=right_sidebar.toggle).classes("fixed bottom-4 right-4 bg-gray-600 text-white px-4 py-2 rounded")
        
        # Assign callback to worker and log it
        if update_table_callback is not None:
            data_fetcher.stock_data_worker.update_callback = update_table_callback
            logger.info("Assigned update_table_callback to OHLCV worker")
        else:
            logger.warning("update_table_callback is None, not assigned to worker")
    
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        ui.notify(f"Error loading dashboard: {e}", type="error")
    
    return update_table_callback

# Initialize shared watchlist and workers
shared_watchlist = Watchlist()
data_fetcher = DataOHLCVFetcher(Watchlist)  # No callback here yet
info_fetcher = DataInfoFetcher(Watchlist)

# Store worker tasks globally
price_task = None
info_task = None

@nicegui_app.on_startup
async def startup():
    global price_task, info_task
    logger.info("Starting application")
    try:
        price_task = asyncio.create_task(data_fetcher.start())
        info_task = asyncio.create_task(info_fetcher.start())
        logger.info("Workers scheduled to start")
    except Exception as e:
        logger.error(f"Error starting workers: {e}")

@nicegui_app.on_shutdown
async def shutdown():
    global price_task, info_task
    logger.info("Shutting down application")
    try:
        if price_task:
            price_task.cancel()
        if info_task:
            info_task.cancel()
        await asyncio.gather(price_task, info_task, return_exceptions=True)
    except Exception as e:
        logger.error(f"Error cancelling worker tasks: {e}")
    print("Shutting down workers...")

if __name__ in {"__main__", "__mp_main__"}:
    logger.info("Starting NiceGUI app")
    ui.run(host="0.0.0.0", port=8000, reload=True)