# workers/data_info_fetcher.py
import asyncio
import yfinance as yf
import pytz
from datetime import datetime
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
info_collection = db["stock_info_details"]

class StockInfoWorker:
    def __init__(self, watchlist_factory, info_collection):
        self.running = False
        self.watchlist_factory = watchlist_factory  # Callable to get fresh Watchlist instance
        self.info_collection = info_collection  # MongoDB collection reference

    async def get_tickers(self) -> List[str]:
        """Get fresh tickers from a new watchlist instance asynchronously."""
        loop = asyncio.get_event_loop()
        # Create a new Watchlist instance each time to get the latest data
        watchlist = await loop.run_in_executor(None, self.watchlist_factory)
        tickers = await loop.run_in_executor(None, lambda: [item["ticker"] for item in watchlist.watchlist_items])
        return tickers

    async def fetch_stock_info(self, ticker: str) -> Optional[Dict]:
        """Fetch detailed stock information from Yahoo Finance asynchronously."""
        loop = asyncio.get_event_loop()
        try:
            stock = await loop.run_in_executor(None, lambda: yf.Ticker(ticker))
            info = await loop.run_in_executor(None, lambda: stock.info)
            if not info or 'symbol' not in info:
                raise ValueError("No info returned")

            pe_ratio = info.get("trailingPE")
            if pe_ratio is None and "currentPrice" in info and "trailingEps" in info and info["trailingEps"] != 0:
                pe_ratio = info["currentPrice"] / info["trailingEps"]

            stock_details = {
                "ticker": ticker,
                "name": info.get("longName", "N/A"),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": info.get("marketCap", None),
                "price_target": info.get("targetMeanPrice", None),
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
                "timestamp": datetime.now(pytz.UTC).isoformat()
            }
            return stock_details
        except Exception as e:
            print(f"Error fetching stock info for {ticker}: {e}")
            return None

    async def update_stock_info(self, ticker: str) -> None:
        """Insert new stock info record into MongoDB asynchronously."""
        info = await self.fetch_stock_info(ticker)
        if info:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.info_collection.insert_one(info))
            print(f"Inserted new stock info record for {ticker} at {info['timestamp']}")
        else:
            print(f"Skipped inserting stock info for {ticker} due to fetch error")

    async def update_batch(self, tickers: List[str]) -> int:
        """Update stock info for multiple tickers concurrently."""
        tasks = [self.update_stock_info(ticker) for ticker in tickers]
        await asyncio.gather(*tasks)
        return len(tickers)

    async def run(self) -> None:
        """Main async worker loop for stock info, updating every 30 minutes."""
        if self.running:
            print("StockInfoFetcher already running, skipping new instance")
            return

        self.running = True
        print(f"StockInfoFetcher Worker started at {datetime.now(pytz.UTC).isoformat()}")

        while self.running:
            try:
                tickers = await self.get_tickers()
                if not tickers:
                    print("No tickers found in watchlist for info update")
                    await asyncio.sleep(1800)  # Sleep for 30 minutes
                    continue

                print(f"Processing stock info for tickers: {tickers}")
                await self.update_batch(tickers)
                print(f"Completed stock info update at {datetime.now(pytz.UTC).isoformat()}")

            except Exception as e:
                print(f"StockInfoWorker error: {e}")

            await asyncio.sleep(1800)  # Update every 30 minutes (1800 seconds)

class DataInfoFetcher:
    def __init__(self, watchlist_factory):
        self.stock_info_worker = StockInfoWorker(watchlist_factory, info_collection)

    async def start(self):
        """Start the worker loop."""
        await self.stock_info_worker.run()

    async def fetch_ticker_info(self, ticker: str) -> Optional[Dict]:
        """Fetch stock info for a specific ticker on demand."""
        return await self.stock_info_worker.fetch_stock_info(ticker)

# Example usage (for testing)
async def main():
    from watchlist import Watchlist  # Replace with actual import
    fetcher = DataInfoFetcher(Watchlist)  # Pass the class
    await fetcher.start()

if __name__ == "__main__":
    asyncio.run(main())