import pymongo
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import time
import pytz
from watchlist import Watchlist

# Load environment variables
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
collection = db["stock_prices"]

def get_watchlist_tickers():
    """Fetch tickers from Watchlist"""
    watchlist = Watchlist()
    return [item["ticker"] for item in watchlist.watchlist_items]

def get_latest_timestamp(stock):
    """Retrieve the latest timestamp for a stock from MongoDB"""
    latest_doc = collection.find_one({"ticker": stock}, sort=[("timestamp", -1)])
    if latest_doc and "timestamp" in latest_doc:
        dt = datetime.fromisoformat(latest_doc["timestamp"])
        if dt.tzinfo is None:
            return pytz.UTC.localize(dt)
        return dt
    return None

def get_missing_timestamps(stock):
    """Identify missing timestamps for today"""
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(pytz.UTC)
    today_start = now.astimezone(eastern).replace(hour=9, minute=30, second=0, microsecond=0).astimezone(pytz.UTC)
    
    existing_timestamps = set(
        doc["timestamp"] for doc in collection.find(
            {"ticker": stock, "timestamp": {"$gte": today_start.isoformat()}}, 
            {"timestamp": 1}
        )
    )
    
    minutes_since_open = int((now - today_start).total_seconds() // 60)
    expected_timestamps = set(
        (today_start + timedelta(minutes=i)).isoformat()
        for i in range(minutes_since_open)
    )
    
    return sorted(expected_timestamps - existing_timestamps)

def backfill_historical_data(stock):
    """Backfill historical data up to yesterday"""
    latest_timestamp = get_latest_timestamp(stock)
    now = datetime.now(pytz.UTC)
    yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)

    if not latest_timestamp or latest_timestamp < yesterday_end:
        start_date = latest_timestamp if latest_timestamp else now - timedelta(days=7)
        print(f"Backfilling historical data for {stock} from {start_date} to {yesterday_end}")
        
        try:
            data = yf.download(stock, start=start_date, end=yesterday_end, interval="1m", auto_adjust=False)
            if data.empty:
                print(f"No historical data available for {stock} from {start_date} to {yesterday_end}.")
                return

            records_inserted = 0
            for timestamp in data.index:
                ohlc = data.loc[timestamp]
                if any(ohlc[["Open", "High", "Low", "Close"]].isna()):
                    continue

                doc = {
                    "timestamp": timestamp.isoformat(),
                    "ticker": stock,
                    "open": round(float(ohlc["Open"].iloc[0]), 2),  # Fixed: Use iloc[0]
                    "high": round(float(ohlc["High"].iloc[0]), 2),  # Fixed: Use iloc[0]
                    "low": round(float(ohlc["Low"].iloc[0]), 2),    # Fixed: Use iloc[0]
                    "close": round(float(ohlc["Close"].iloc[0]), 2), # Fixed: Use iloc[0]
                }
                collection.update_one(
                    {"timestamp": doc["timestamp"], "ticker": stock},
                    {"$set": doc},
                    upsert=True
                )
                records_inserted += 1
            print(f"Backfilled {records_inserted} historical records for {stock}.")
        except Exception as e:
            print(f"Error backfilling historical data for {stock}: {e}")

def backfill_today_data(stock):
    """Backfill missing data for today"""
    missing_timestamps = get_missing_timestamps(stock)
    if not missing_timestamps:
        print(f"No missing data to backfill for {stock} today.")
        return

    print(f"Backfilling {len(missing_timestamps)} missing records for {stock} today")
    start_date = missing_timestamps[0].split("T")[0]
    end_date = (datetime.now(pytz.UTC) + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        data = yf.download(stock, start=start_date, end=end_date, interval="1m", auto_adjust=False)
        if data.empty:
            print(f"No data available to backfill today for {stock} from {start_date} to {end_date}.")
            return

        records_inserted = 0
        for timestamp in data.index:
            ohlc = data.loc[timestamp]
            if any(ohlc[["Open", "High", "Low", "Close"]].isna()):
                print(f"Skipping {stock} at {timestamp}, missing OHLC data.")
                continue

            doc = {
                "timestamp": timestamp.isoformat(),
                "ticker": stock,
                "open": round(float(ohlc["Open"].iloc[0]), 2),  # Fixed: Use iloc[0]
                "high": round(float(ohlc["High"].iloc[0]), 2),  # Fixed: Use iloc[0]
                "low": round(float(ohlc["Low"].iloc[0]), 2),    # Fixed: Use iloc[0]
                "close": round(float(ohlc["Close"].iloc[0]), 2), # Fixed: Use iloc[0]
            }
            collection.update_one(
                {"timestamp": doc["timestamp"], "ticker": stock},
                {"$set": doc},
                upsert=True
            )
            records_inserted += 1
        print(f"Backfilled {records_inserted} records for {stock} today.")
    except Exception as e:
        print(f"Error backfilling today’s data for {stock}: {e}")

def update_mongo():
    """Worker to update MongoDB with stock data"""
    print(f"Worker started at {datetime.now(pytz.UTC).isoformat()}")

    while True:
        try:
            stocks = get_watchlist_tickers()
            if not stocks:
                print("No tickers found in the watchlist.")
                time.sleep(60)
                continue

            print(f"Fetching data for: {stocks}")

            for stock in stocks:
                backfill_historical_data(stock)
                backfill_today_data(stock)
                time.sleep(1)

            data = yf.download(stocks, period="1d", interval="1m", group_by="ticker", prepost=False, threads=True)
            if data.empty:
                print(f"No current day data returned from yfinance for {stocks}")
                print(f"Attempted fetch at {datetime.now(pytz.UTC).isoformat()}")
                time.sleep(60)
                continue

            records_inserted = 0
            for timestamp in data.index:
                for stock in stocks:
                    try:
                        if len(stocks) > 1:
                            ohlc = (
                                data[("Open", stock)][timestamp],
                                data[("High", stock)][timestamp],
                                data[("Low", stock)][timestamp],
                                data[("Close", stock)][timestamp]
                            )
                        else:
                            ohlc = (
                                data["Open"][timestamp],
                                data["High"][timestamp],
                                data["Low"][timestamp],
                                data["Close"][timestamp]
                            )

                        if any(pd.isna(x) for x in ohlc):
                            print(f"Skipping {stock} at {timestamp}, missing OHLC data.")
                            continue

                        doc = {
                            "timestamp": timestamp.isoformat(),
                            "ticker": stock,
                            "open": round(float(ohlc[0]), 2),  # Already scalar, no iloc needed
                            "high": round(float(ohlc[1]), 2),  # Already scalar, no iloc needed
                            "low": round(float(ohlc[2]), 2),   # Already scalar, no iloc needed
                            "close": round(float(ohlc[3]), 2), # Already scalar, no iloc needed
                        }
                        collection.update_one(
                            {"timestamp": doc["timestamp"], "ticker": stock},
                            {"$set": doc},
                            upsert=True
                        )
                        records_inserted += 1
                    except KeyError:
                        print(f"Skipping {stock}, missing data for timestamp {timestamp}")

            print(f"Updated MongoDB with {records_inserted} new entries at {datetime.now(pytz.UTC).isoformat()}")

        except Exception as e:
            print(f"Worker error: {e}")
        
        time.sleep(60)

if __name__ == "__main__":
    update_mongo()