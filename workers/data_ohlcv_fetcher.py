# workers/data_ohlcv_fetcher.py
import asyncio
import aiohttp
import pandas as pd
import yfinance as yf
import pytz
from datetime import datetime, timedelta, date, timezone
import pymongo
from typing import List, Dict, Optional
from dotenv import load_dotenv
import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time
from alpaca.trading.client import TradingClient
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.historical.corporate_actions import CorporateActionsClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.trading.stream import TradingStream
from alpaca.data.live.stock import StockDataStream

from alpaca.data.requests import (
    CorporateActionsRequest,
    StockBarsRequest,
    StockQuotesRequest,
    StockTradesRequest,
)
from alpaca.trading.requests import (
    ClosePositionRequest,
    GetAssetsRequest,
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopLossRequest,
    StopOrderRequest,
    TakeProfitRequest,
    TrailingStopOrderRequest,
)
from alpaca.trading.enums import (
    AssetExchange,
    AssetStatus,
    OrderClass,
    OrderSide,
    OrderType,
    QueryOrderStatus,
    TimeInForce,
)

# setup clients
trade_client = TradingClient(api_key=os.getenv("ALPACA_API_KEY"), secret_key=os.getenv("ALPACA_SECRET_KEY"), paper=True)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
        self.retry_delay = 60  # Seconds to wait on rate limit or API errors

    async def get_tickers(self) -> List[str]:
        loop = asyncio.get_event_loop()
        watchlist = await loop.run_in_executor(None, self.watchlist_factory)
        tickers = await loop.run_in_executor(None, lambda: [item["ticker"] for item in watchlist.watchlist_items])
        return tickers

    async def get_latest_timestamp(self, ticker: str) -> Optional[datetime]:
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, lambda: self.collection.find_one({"ticker": ticker}, sort=[("timestamp", -1)]))
        if doc and "timestamp" in doc:
            try:
                # Handle the timestamp format "2025-02-27T20:59:00+00:00Z" by removing 'Z' and parsing
                timestamp_str = doc["timestamp"].rstrip("Z")
                dt = datetime.fromisoformat(timestamp_str)
                if dt.tzinfo is None:
                    dt = pytz.UTC.localize(dt)  # Ensure UTC if no timezone
                return dt
            except ValueError as e:
                logger.error(f"Invalid timestamp format for {ticker}: {doc['timestamp']}, error: {e}")
                return None
        return None

    async def fetch_yahoo_data(self, tickers: str | List[str], start=None, end=None, interval="1m") -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                today = date.today()  # Feb 27, 2025
                if start is None and end is None:
                    start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
                    end = datetime.now(tz=timezone.utc)
                    logger.debug(f"Fetching real-time data for {tickers} from {start} to {end}")

                data = await loop.run_in_executor(None, lambda: yf.download(
                    tickers, start=start, end=end, interval=interval, auto_adjust=False, threads=True, progress=False
                ))
                if not data.empty:
                    return data
                else:
                    logger.warning(f"No data available for {tickers} at {datetime.now(pytz.UTC).isoformat()}")
                    await asyncio.sleep(1)  # Short delay before retry
                    retry_count += 1
                    continue
            except Exception as e:
                logger.error(f"Error fetching Yahoo data for {tickers}: {e}")
                if "rate limit" in str(e).lower() or "429" in str(e):
                    logger.warning(f"Rate limit hit for {tickers}, retrying in {self.retry_delay} seconds")
                    await asyncio.sleep(self.retry_delay)
                    retry_count += 1
                    continue
                return pd.DataFrame()  # Return empty on non-rate-limit errors

        logger.error(f"Max retries reached for {tickers}, no data fetched")
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
                    "timestamp": timestamp.isoformat() + "Z",
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

    async def update_current(self, tickers: List[str]) -> int:
        today = date.today()  # Feb 27, 2025
        start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        now = datetime.now(pytz.UTC)

        data = await self.fetch_yahoo_data(tickers, start, now)
        if data.empty:
            logger.warning(f"No current data available for {tickers} on {today}")
            return 0

        total = 0
        multi_ticker = len(tickers) > 1
        tasks = [self.process_ohlc_data(ticker, data, multi_ticker) for ticker in tickers]
        results = await asyncio.gather(*tasks)
        total = sum(results)
        if self.update_callback and total > 0:
            await self.update_callback()
        logger.info(f"Updated {total} real-time records for {tickers} on {today}")
        return total

    async def run(self) -> None:
        if self.running:
            logger.info("StockOHLCVFetcher Worker already running, skipping new instance")
            return

        self.running = True
        logger.info(f"StockOHLCVFetcher Worker started at {datetime.now(pytz.UTC).isoformat()}")

        # Use AsyncIOScheduler for scheduling every minute, 24/7
        async def scheduled_update():
            tickers = await self.get_tickers()
            if tickers:
                await self.update_current(tickers)

        scheduler = AsyncIOScheduler()
        scheduler.add_job(scheduled_update, 'interval', minutes=1)
        scheduler.start()

        try:
            # Initial update to fetch today’s data
            tickers = await self.get_tickers()
            if tickers:
                await self.update_current(tickers)

            # Keep the script running
            while self.running:
                await asyncio.sleep(60)  # Keep the loop alive, scheduler handles timing
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            scheduler.shutdown()
            self.running = False
            logger.info("StockOHLCVFetcher Worker stopped")

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
    from components.watchlist_card import Watchlist
    fetcher = DataOHLCVFetcher(Watchlist)
    await fetcher.start()

if __name__ == "__main__":
    asyncio.run(main())