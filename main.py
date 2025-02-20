# main.py
from nicegui import ui, app as nicegui_app
from api import app as api_app
from dashboard import create_dashboard

# Mount the API routes at /api
nicegui_app.mount("/api", api_app)

# Shared header navigation
def create_header():
    with ui.header().classes("bg-gray-800 text-white p-4 flex justify-between items-center"):
        ui.label("Trading Dashboard").classes("text-xl font-bold")
        with ui.row().classes("gap-4"):
            ui.button("Home", on_click=lambda: ui.navigate.to("/")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("About", on_click=lambda: ui.notify("About page coming soon!")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")
            ui.button("Settings", on_click=lambda: ui.notify("Settings page coming soon!")).classes("bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded")

# Homepage at /
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
                ui.button("Settings", on_click=lambda: ui.notify("Settings page coming soon!")).classes("w-full")
        ui.label("Powered by NiceGUI & xAI").classes("text-sm text-gray-500 mt-4 text-center")

# Dashboard at /dashboard
@ui.page("/dashboard")
def dashboard_page():
    create_header()
    with ui.card().classes("w-full max-w-4xl mx-auto p-4"):
        create_dashboard()
    # Right-hand sidebar (top-level element)
    with ui.right_drawer(fixed=True).classes("bg-gray-100 p-4 w-1/4") as sidebar:
        ui.label("Dashboard Sidebar").classes("text-xl font-semibold mb-4")
        ui.label("Additional Info").classes("text-lg mb-2")
        ui.label("Coming Soon:").classes("text-sm text-gray-600")
        ui.label("- Stock Details").classes("text-sm")
        ui.label("- Quick Actions").classes("text-sm")
        ui.button("Toggle Sidebar", on_click=sidebar.toggle).classes("mt-4")
    # Use toggle instead of open for the external button
    ui.button("Toggle Sidebar", on_click=sidebar.toggle).classes("fixed bottom-4 right-4")

# Run the app with NiceGUI
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="0.0.0.0", port=8000)