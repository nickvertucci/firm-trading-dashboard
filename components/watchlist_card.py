# components/watchlist_card.py
from nicegui import ui
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import pymongo
import asyncio

# Load environment variables
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
watchlist_collection = db["stock_watchlist"]

class Watchlist:
    def __init__(self):
        self.watchlist_items = []
        self._callbacks = []  # List to store update callbacks
        self.load_watchlist()

    def load_watchlist(self):
        """Load watchlist from MongoDB"""
        self.watchlist_items = list(watchlist_collection.find())
        if not self.watchlist_items:
            self.watchlist_items = []

    def add_callback(self, callback):
        """Register a callback to be called when the watchlist changes."""
        self._callbacks.append(callback)

    async def _notify_callbacks(self):
        """Notify all registered callbacks of a change, awaiting async ones."""
        for callback in self._callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback()  # Await async callbacks
            else:
                callback()  # Call sync callbacks directly

    def add_ticker(self, ticker):
        """Add a ticker to watchlist and notify callbacks."""
        if ticker and ticker.upper() not in [item.get('ticker', '').upper() for item in self.watchlist_items]:
            ticker_data = {'ticker': ticker.upper()}
            watchlist_collection.insert_one(ticker_data)
            self.watchlist_items.append(ticker_data)
            # Since this is called from a button (sync context), schedule async notification
            asyncio.create_task(self._notify_callbacks())

    def delete_ticker(self, ticker):
        """Delete a ticker from watchlist and notify callbacks."""
        watchlist_collection.delete_one({'ticker': ticker})
        self.watchlist_items = [item for item in self.watchlist_items if item['ticker'] != ticker]
        # Since this is called from a button (sync context), schedule async notification
        asyncio.create_task(self._notify_callbacks())

def watchlist_card():
    """Create a card component for the watchlist"""
    watchlist = Watchlist()  # Instantiate the Watchlist class
    with ui.card().classes("w-64 p-4 shadow-md"):
        ui.label("Firm Watchlist").classes("text-lg font-semibold mb-2")
        with ui.column().classes("w-full"):
            # Input for adding new tickers
            with ui.row().classes("w-full items-center"):
                ticker_input = ui.input(placeholder="Add Ticker").classes("flex-grow")
                ui.button(
                    "Add",
                    on_click=lambda: (watchlist.add_ticker(ticker_input.value), ticker_input.set_value(""))
                ).classes("ml-2")

            # Watchlist display
            watchlist_container = ui.column().classes("w-full")

            def refresh_ui():
                """Refresh the watchlist display"""
                watchlist_container.clear()
                with watchlist_container:
                    if not watchlist.watchlist_items:
                        ui.label("Watchlist is empty").classes("text-gray-600 text-sm")
                    else:
                        for item in watchlist.watchlist_items:
                            with ui.row().classes("w-full items-center"):
                                ui.label(item["ticker"]).classes("flex-grow text-sm")
                                ui.button(
                                    "Delete",
                                    on_click=lambda x=item["ticker"]: watchlist.delete_ticker(x),
                                    color="red"
                                ).classes("ml-2 text-xs")

            # Initial render and bind refresh to watchlist updates
            refresh_ui()
            watchlist.add_callback(refresh_ui)  # Sync callback for UI refresh

    return watchlist  # Return the Watchlist instance for external use

# Example usage (for standalone testing)
if __name__ == "__main__":
    watchlist_instance = watchlist_card()
    ui.run()