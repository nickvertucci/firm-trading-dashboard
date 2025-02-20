# data.py
import pymongo
from dotenv import load_dotenv
import os
from datetime import datetime
from watchlist import Watchlist  # Import Watchlist

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
collection = db["stock_prices"]

def get_stock_data():
    try:

        # Initialize watchlist
        watchlist = Watchlist()
        tickers = [item["ticker"] for item in watchlist.watchlist_items]
        
        if not tickers:  # If watchlist is empty, return empty list or default behavior
            return []
        
        # Fetch all data for today from MongoDB for watchlist tickers
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        query_filter = {
            "timestamp": {"$gte": today},
            "ticker": {"$in": tickers}
        }
                
        cursor = collection.find(query_filter).sort("timestamp", pymongo.ASCENDING)
        
        result = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        
        return result
    
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []
