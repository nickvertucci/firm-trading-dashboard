# watchlist.py
from nicegui import ui
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import pymongo


# Load environment variables
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
watchlist_collection = db["stock_watchlist"]

class Watchlist:
    def __init__(self):
        self.watchlist_items = []
        self.load_watchlist()

    def load_watchlist(self):
        """Load watchlist from MongoDB"""
        self.watchlist_items = list(watchlist_collection.find())
        if not self.watchlist_items:
            self.watchlist_items = []

    def add_ticker(self, ticker):
        """Add a ticker to watchlist"""
        if ticker and ticker.upper() not in [item.get('ticker', '').upper() for item in self.watchlist_items]:
            ticker_data = {'ticker': ticker.upper()}
            watchlist_collection.insert_one(ticker_data)
            self.watchlist_items.append(ticker_data)
            self.refresh_ui()

    def delete_ticker(self, ticker):
        """Delete a ticker from watchlist"""
        watchlist_collection.delete_one({'ticker': ticker})
        self.watchlist_items = [item for item in self.watchlist_items if item['ticker'] != ticker]
        self.refresh_ui()

    def build(self):
        """Build the watchlist UI component"""
        with ui.column().classes('w-full'):
            # Input for adding new tickers
            with ui.row().classes('w-full items-center'):
                ticker_input = ui.input('Add Ticker').classes('flex-grow')
                ui.button('Add', on_click=lambda: self.add_ticker(ticker_input.value)).classes('ml-2')
            
            # Watchlist display
            with ui.column() as self.watchlist_container:
                self.refresh_ui()

    def refresh_ui(self):
        """Refresh the watchlist display"""
        if hasattr(self, 'watchlist_container'):
            self.watchlist_container.clear()
            with self.watchlist_container:
                if not self.watchlist_items:
                    ui.label('Watchlist is empty')
                else:
                    for item in self.watchlist_items:
                        with ui.row().classes('w-full items-center'):
                            ui.label(item['ticker']).classes('flex-grow')
                            ui.button('Delete', 
                                    on_click=lambda x=item['ticker']: self.delete_ticker(x),
                                    color='red').classes('ml-2')