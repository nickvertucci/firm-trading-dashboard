# data.py
import pymongo
import yfinance as yf
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
collection = db["stock_prices"]

def get_stock_data():
    stocks = ["AAPL", "GOOGL", "TSLA"]
    
    try:
        # Fetch full day's 1-minute OHLC data
        data = yf.download(stocks, period="1d", interval="1m")
        if data.empty:
            print("No data returned from yfinance")
            fallback = [{"symbol": s, "open": 150.0, "high": 155.0, "low": 145.0, "close": 152.0, "timestamp": datetime.now().isoformat()} for s in stocks]
            print(f"Fallback data: {fallback}")
            return fallback
        
        # Get all existing timestamps from MongoDB for today
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        existing_docs = collection.find({"timestamp": {"$gte": today}})
        stored_timestamps = {doc["timestamp"] for doc in existing_docs}
        
        # Backfill missing or incomplete data
        for timestamp in data.index:
            ts_str = timestamp.isoformat()
            doc = {"timestamp": ts_str}
            for stock in stocks:
                ohlc = data["Open"][stock][timestamp], data["High"][stock][timestamp], data["Low"][stock][timestamp], data["Close"][stock][timestamp]
                if not any(pd.isna(x) for x in ohlc):
                    doc[stock] = {
                        "open": round(ohlc[0], 2),
                        "high": round(ohlc[1], 2),
                        "low": round(ohlc[2], 2),
                        "close": round(ohlc[3], 2)
                    }
            # Insert or update regardless of latest_time to backfill gaps
            collection.update_one({"timestamp": doc["timestamp"]}, {"$set": doc}, upsert=True)
            if ts_str not in stored_timestamps:
                print(f"Backfilled: {ts_str}")
        
        # Fetch all data for the day from MongoDB
        cursor = collection.find({"timestamp": {"$gte": today}}).sort("timestamp", pymongo.ASCENDING)
        result = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        return result if result else [{"symbol": s, "open": 150.0, "high": 155.0, "low": 145.0, "close": 152.0, "timestamp": datetime.now().isoformat()} for s in stocks]
    
    except Exception as e:
        print(f"Error fetching/storing data: {e}")
        fallback = [{"symbol": s, "open": 150.0, "high": 155.0, "low": 145.0, "close": 152.0, "timestamp": datetime.now().isoformat()} for s in stocks]
        print(f"Returning fallback data due to error: {fallback}")
        return fallback