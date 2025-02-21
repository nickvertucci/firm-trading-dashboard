# workers/data_ohlcv_fetcher.py
import asyncio
import aiohttp
import pandas as pd
import yfinance as yf
import pytz
from datetime import datetime, timedelta
import pymongo
from typing import List, Dict, Optional
from dotenv import load_dotenv
import os

# Initialize MongoDB connection
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    raise ValueError("MONGO_URI not found in .env file")

client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
collection = db["stock_prices"]

class StockDataWorker:
    def __init__(self, watchlist_factory, collection, update_callback=None):
        self.eastern = pytz.timezone('US/Eastern')
        self.running = False
        self.watchlist_factory = watchlist_factory
        self.collection = collection
        self.update_callback = update_callback  # Callback to notify dashboard

    async def get_tickers(self) -> List[str]:
        loop = asyncio.get_event_loop()
        watchlist = await loop.run_in_executor(None, self.watchlist_factory)
        tickers = await loop.run_in_executor(None, lambda: [item["ticker"] for item in watchlist.watchlist_items])
        return tickers

    async def get_latest_timestamp(self, ticker: str) -> Optional[datetime]:
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, lambda: self.collection.find_one({"ticker": ticker}, sort=[("timestamp", -1)]))
        if doc and "timestamp" in doc:
            dt = datetime.fromisoformat(doc["timestamp"])
            return pytz.UTC.localize(dt) if dt.tzinfo is None else dt
        return None

    async def fetch_yahoo_data(self, tickers: str | List[str], start=None, end=None, interval="1m") -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        try:
            if start is None and end is None:
                data = await loop.run_in_executor(None, lambda: yf.download(
                    tickers, period="2d", interval=interval, auto_adjust=False, threads=True, progress=False
                ))
            else:
                data = await loop.run_in_executor(None, lambda: yf.download(
                    tickers, start=start, end=end, interval=interval, auto_adjust=False, threads=True, progress=False
                ))
            return data
        except Exception as e:
            print(f"Error fetching Yahoo data: {e}")
            return pd.DataFrame()

    async def process_ohlc_data(self, ticker: str, data: pd.DataFrame, multi_ticker: bool = True) -> int:
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

                volume = (
                    data[("Volume", ticker)][timestamp] if multi_ticker else data["Volume"][timestamp]
                )
                volume = int(volume) if pd.notna(volume) else 0

                doc = {
                    "timestamp": timestamp.isoformat(),
                    "ticker": ticker,
                    "open": round(float(ohlc[0]), 2),
                    "high": round(float(ohlc[1]), 2),
                    "low": round(float(ohlc[2]), 2),
                    "close": round(float(ohlc[3]), 2),
                    "volume": volume
                }
                records.append(doc)
            except KeyError:
                continue

        if records:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.collection.bulk_write(
                [pymongo.UpdateOne(
                    {"timestamp": doc["timestamp"], "ticker": ticker},
                    {"$set": doc},
                    upsert=True
                ) for doc in records]
            ))
            return len(records)
        return 0

    async def needs_historical_backfill(self, ticker: str) -> bool:
        latest = await self.get_latest_timestamp(ticker)
        now = datetime.now(pytz.UTC)
        yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        return not latest or latest < yesterday_end

    async def backfill_historical(self, ticker: str) -> None:
        if not await self.needs_historical_backfill(ticker):
            return

        latest = await self.get_latest_timestamp(ticker)
        now = datetime.now(pytz.UTC)
        yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        start = latest or (now - timedelta(days=7))

        data = await self.fetch_yahoo_data(ticker, start, yesterday_end)
        if not data.empty:
            count = await self.process_ohlc_data(ticker, data, multi_ticker=False)
            print(f"Backfilled {count} historical records for {ticker}")
            if self.update_callback and count > 0:
                await self.update_callback()

    async def needs_today_backfill(self, ticker: str) -> bool:
        now = datetime.now(pytz.UTC)
        today_start = now.astimezone(self.eastern).replace(hour=9, minute=30, second=0, microsecond=0).astimezone(pytz.UTC)
        if now < today_start:
            return False
        latest = await self.get_latest_timestamp(ticker)
        return not latest or latest < today_start

    async def backfill_today(self, ticker: str) -> None:
        if not await self.needs_today_backfill(ticker):
            return

        now = datetime.now(pytz.UTC)
        today_start = now.astimezone(self.eastern).replace(hour=9, minute=30, second=0, microsecond=0).astimezone(pytz.UTC)
        data = await self.fetch_yahoo_data(ticker, today_start.date(), now.date() + timedelta(days=1))
        if not data.empty:
            count = await self.process_ohlc_data(ticker, data, multi_ticker=False)
            print(f"Backfilled {count} records for {ticker} today")
            if self.update_callback and count > 0:
                await self.update_callback()

    async def update_current(self, tickers: List[str]) -> int:
        data = await self.fetch_yahoo_data(tickers)
        if data.empty:
            print(f"No current data available for {tickers}")
            return 0

        total = 0
        multi_ticker = len(tickers) > 1
        tasks = [self.process_ohlc_data(ticker, data, multi_ticker) for ticker in tickers]
        results = await asyncio.gather(*tasks)
        total = sum(results)
        if self.update_callback and total > 0:
            await self.update_callback()
        return total

    async def run(self) -> None:
        if self.running:
            print("StockOHLCVFetcher Worker already running, skipping new instance")
            return

        self.running = True
        print(f"StockOHLCVFetcher Worker started at {datetime.now(pytz.UTC).isoformat()}")

        while self.running:
            try:
                tickers = await self.get_tickers()
                if not tickers:
                    print("No tickers found in watchlist")
                    await asyncio.sleep(60)
                    continue

                print(f"Processing tickers: {tickers}")
                backfill_tasks = [
                    asyncio.gather(self.backfill_historical(ticker), self.backfill_today(ticker))
                    for ticker in tickers
                ]
                await asyncio.gather(*backfill_tasks)

                count = await self.update_current(tickers)
                print(f"Updated {count} records at {datetime.now(pytz.UTC).isoformat()}")

            except Exception as e:
                print(f"Worker error: {e}")

            await asyncio.sleep(60)

class DataOHLCVFetcher:
    def __init__(self, watchlist_factory, update_callback=None):
        self.stock_data_worker = StockDataWorker(watchlist_factory, collection, update_callback)

    async def start(self):
        """Start the worker loop."""
        await self.stock_data_worker.run()

    async def fetch_ticker_data(self, ticker: str, start=None, end=None, interval="1m") -> pd.DataFrame:
        """Fetch data for a specific ticker on demand."""
        return await self.stock_data_worker.fetch_yahoo_data(ticker, start, end, interval)

# Example usage (for testing)
async def main():
    from watchlist import Watchlist
    fetcher = DataOHLCVFetcher(Watchlist)
    await fetcher.start()

if __name__ == "__main__":
    asyncio.run(main())