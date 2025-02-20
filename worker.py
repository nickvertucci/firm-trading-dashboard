import pymongo
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import time
import pytz
from watchlist import Watchlist
from alpaca.trading.client import TradingClient
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Initialize Alpaca client
trading_client = TradingClient(api_key=os.getenv("ALPACA_API_KEY"), secret_key=os.getenv("ALPACA_SECRET_KEY"))
stock_historical_data = StockHistoricalDataClient(api_key=os.getenv("ALPACA_API_KEY"), secret_key=os.getenv("ALPACA_SECRET_KEY"))   

# Initialize MongoDB connection
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
collection = db["stock_prices"]
info_collection = db["stock_info_details"]

class StockDataWorker:
    def __init__(self):
        self.eastern = pytz.timezone('US/Eastern')
        self.running = False  # Flag to prevent multiple instances

    def get_tickers(self):
        """Get fresh tickers from watchlist each time"""
        watchlist = Watchlist()  # Create new instance to get latest data
        return [item["ticker"] for item in watchlist.watchlist_items]

    def get_latest_timestamp(self, ticker):
        """Get latest stored timestamp for a ticker"""
        doc = collection.find_one({"ticker": ticker}, sort=[("timestamp", -1)])
        if doc and "timestamp" in doc:
            dt = datetime.fromisoformat(doc["timestamp"])
            return pytz.UTC.localize(dt) if dt.tzinfo is None else dt
        return None

    def fetch_yahoo_data(self, tickers, start=None, end=None, interval="1m"):
        """Centralized Yahoo Finance data fetching"""
        try:
            if start is None and end is None:
                data = yf.download(
                    tickers, 
                    period="2d",
                    interval=interval, 
                    auto_adjust=False, 
                    threads=True
                )
            else:
                data = yf.download(
                    tickers, 
                    start=start, 
                    end=end, 
                    interval=interval, 
                    auto_adjust=False, 
                    threads=True
                )
            return data
        except Exception as e:
            print(f"Error fetching Yahoo data: {e}")
            return pd.DataFrame()  # Return empty DataFrame on error

    def process_ohlc_data(self, ticker, data, multi_ticker=True):
        """Process OHLC data and store in MongoDB"""
        if data.empty:
            return 0
            
        records = []
        for timestamp in data.index:
            try:
                ohlc = (
                    data[("Open", ticker)][timestamp] if multi_ticker else data["Open"][timestamp],
                    data[("High", ticker)][timestamp] if multi_ticker else data["High"][timestamp],
                    data[("Low", ticker)][timestamp] if multi_ticker else data["Low"][timestamp],
                    data[("Close", ticker)][timestamp] if multi_ticker else data["Close"][timestamp]
                )
                if any(pd.isna(x) for x in ohlc):
                    continue

                doc = {
                    "timestamp": timestamp.isoformat(),
                    "ticker": ticker,
                    "open": round(float(ohlc[0]), 2),
                    "high": round(float(ohlc[1]), 2),
                    "low": round(float(ohlc[2]), 2),
                    "close": round(float(ohlc[3]), 2)
                }
                records.append(doc)
            except KeyError:
                continue
        
        if records:
            collection.bulk_write(
                [pymongo.UpdateOne(
                    {"timestamp": doc["timestamp"], "ticker": ticker},
                    {"$set": doc},
                    upsert=True
                ) for doc in records]
            )
            return len(records)
        return 0

    def needs_historical_backfill(self, ticker):
        """Check if historical backfill is needed"""
        latest = self.get_latest_timestamp(ticker)
        now = datetime.now(pytz.UTC)
        yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        return not latest or latest < yesterday_end

    def backfill_historical(self, ticker):
        """Backfill historical data up to yesterday if needed"""
        if not self.needs_historical_backfill(ticker):
            print(f"No historical backfill needed for {ticker}")
            return

        latest = self.get_latest_timestamp(ticker)
        now = datetime.now(pytz.UTC)
        yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        start = latest or (now - timedelta(days=7))

        data = self.fetch_yahoo_data(ticker, start, yesterday_end)
        if not data.empty:
            count = self.process_ohlc_data(ticker, data, multi_ticker=False)
            print(f"Backfilled {count} historical records for {ticker}")
        else:
            print(f"No historical data available to backfill for {ticker}")

    def needs_today_backfill(self, ticker):
        """Check if today's data needs backfilling"""
        now = datetime.now(pytz.UTC)
        today_start = now.astimezone(self.eastern).replace(hour=9, minute=30, second=0, microsecond=0).astimezone(pytz.UTC)
        
        if now < today_start:
            return False
        
        latest = self.get_latest_timestamp(ticker)
        return not latest or latest < today_start

    def backfill_today(self, ticker):
        """Backfill today's missing data if needed"""
        if not self.needs_today_backfill(ticker):
            print(f"No backfill needed for {ticker} today")
            return

        now = datetime.now(pytz.UTC)
        today_start = now.astimezone(self.eastern).replace(hour=9, minute=30, second=0, microsecond=0).astimezone(pytz.UTC)
        
        data = self.fetch_yahoo_data(ticker, today_start.date(), now.date() + timedelta(days=1))
        if not data.empty:
            count = self.process_ohlc_data(ticker, data, multi_ticker=False)
            print(f"Backfilled {count} records for {ticker} today")
        else:
            print(f"No data available to backfill today for {ticker}")

    def update_current(self, tickers):
        """Update current day's data"""
        data = self.fetch_yahoo_data(tickers)  # No start/end for current day
        if data.empty:
            print(f"No current data available for {tickers}")
            return 0

        total = 0
        multi_ticker = len(tickers) > 1
        for ticker in tickers:
            total += self.process_ohlc_data(ticker, data, multi_ticker)
        return total

    def run(self):
        """Main worker loop"""
        if self.running:
            print("Worker already running, skipping new instance")
            return
            
        self.running = True
        print(f"Worker started at {datetime.now(pytz.UTC).isoformat()}")
        while self.running:
            try:
                tickers = self.get_tickers()  # Refresh tickers each loop
                if not tickers:
                    print("No tickers found in watchlist")
                    time.sleep(60)
                    continue

                print(f"Processing tickers: {tickers}")  # Debug output
                # Process each ticker
                for ticker in tickers:
                    self.backfill_historical(ticker)
                    self.backfill_today(ticker)

                # Update current data
                count = self.update_current(tickers)
                print(f"Updated {count} records at {datetime.now(pytz.UTC).isoformat()}")

            except Exception as e:
                print(f"Worker error: {e}")
            
            time.sleep(60)

class StockInfoWorker:
    def __init__(self):
        self.running = False

    def get_tickers(self):
        """Get fresh tickers from watchlist each time"""
        watchlist = Watchlist()
        return [item["ticker"] for item in watchlist.watchlist_items]

    def fetch_stock_info(self, ticker):
        """Fetch detailed stock information from Yahoo Finance"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if not info or 'symbol' not in info:
                raise ValueError("No info returned")
            
            pe_ratio = info.get("trailingPE")
            if pe_ratio is None and "currentPrice" in info and "trailingEps" in info and info["trailingEps"] != 0:
                pe_ratio = info["currentPrice"] / info["trailingEps"]
            
            # Select key fields to store - you can adjust these
            stock_details = {
                "ticker": ticker,
                "name": info.get("longName", "N/A"),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": info.get("marketCap", None),
                "price_target": info.get("targetMeanPrice", None),  # Corrected from analyst_price_targets
                "pe_ratio": pe_ratio,
                "dividend_yield": info.get("dividendYield", None),
                "volume": info.get("volume", None),
                "averageVolume10days": info.get("averageVolume10days", None),
                "floatShares": info.get("floatShares", None),
                "fiftyTwoWeekRange": info.get("fiftyTwoWeekRange", "N/A"),
                "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow", None),
                "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh", None),
                "fiftyDayAverage": info.get("fiftyDayAverage", None),
                "twoHundredDayAverage": info.get("twoHundredDayAverage", None),
                "timestamp": datetime.now(pytz.UTC).isoformat()  # Changed to timestamp for new records
            }
            return stock_details
        except Exception as e:
            print(f"Error fetching stock info for {ticker}: {e}")
            return None

    def update_stock_info(self, ticker):
        """Insert new stock info record into MongoDB"""
        info = self.fetch_stock_info(ticker)
        if info:
            info_collection.insert_one(info)  # Insert new document instead of updating
            print(f"Inserted new stock info record for {ticker} at {info['timestamp']}")
        else:
            print(f"Skipped inserting stock info for {ticker} due to fetch error")

    def run(self):
        """Main worker loop for stock info, updating every 30 minutes"""
        if self.running:
            print("StockInfoWorker already running, skipping new instance")
            return
            
        self.running = True
        print(f"StockInfoWorker started at {datetime.now(pytz.UTC).isoformat()}")
        while self.running:
            try:
                tickers = self.get_tickers()
                if not tickers:
                    print("No tickers found in watchlist for info update")
                    time.sleep(1800)  # Sleep for 30 minutes
                    continue

                print(f"Processing stock info for tickers: {tickers}")
                for ticker in tickers:
                    self.update_stock_info(ticker)

                print(f"Completed stock info update at {datetime.now(pytz.UTC).isoformat()}")

            except Exception as e:
                print(f"StockInfoWorker error: {e}")
            
            time.sleep(1800)  # Update every 30 minutes (1800 seconds)


if __name__ == "__main__":
    # For testing, you can run either worker
    price_worker = StockDataWorker()
    info_worker = StockInfoWorker()
    price_worker.run() 
    info_worker.run()