# main.py
from nicegui import ui, app as nicegui_app
from api import app as api_app
from ui import create_dashboard

# Mount the API routes at /api using NiceGUI's FastAPI app
nicegui_app.mount("/api", api_app)

# Define the root endpoint
@nicegui_app.get("/")
async def root():
    return {"message": "Visit /ui for the dashboard"}

# Define the UI at /ui
@ui.page("/ui")
def ui_page():
    with ui.card():
        create_dashboard()

# Run the app with NiceGUI
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="0.0.0.0", port=8000)