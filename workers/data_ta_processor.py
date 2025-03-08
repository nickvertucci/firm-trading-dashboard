# workers/data_ta_processor.py
import asyncio
import pandas as pd
from datetime import datetime, timedelta
import os
from typing import List, Dict
from dotenv import load_dotenv
from tqdm.asyncio import tqdm
import pymongo
from alpaca.trading.client import TradingClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.enums import DataFeed
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetExchange, AssetStatus
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

# Load environment variables
load_dotenv()

# Initialize MongoDB connection
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    raise ValueError("MONGO_URI not found in .env file")

client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
collection = db["stock_ta"]

class TAScanner:
    """Technical Analysis Scanner for stock data with MongoDB storage"""

    def __init__(self):
        # Setup Alpaca clients
        self.trade_client = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
            paper=True
        )
        self.stock_historical_data_client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY")
        )
        self.symbols = []

    async def get_active_assets(self) -> List[Dict]:
        """Get all active US equity assets (no periods in symbol, optional limit)"""
        assets = self.trade_client.get_all_assets(GetAssetsRequest(
            status=AssetStatus.ACTIVE,
            asset_class="us_equity"
        ))
        filtered_assets = [
            asset.__dict__ 
            for asset in assets 
            if asset.tradable 
            and asset.exchange in [AssetExchange.NASDAQ] 
            and '.' not in asset.symbol  # Exclude symbols with periods
        ]
        return filtered_assets  # Optional: Add [:10] for testing

    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Exponential Moving Average for given period"""
        return df['close'].ewm(span=period, adjust=False).mean()

    async def fetch_bar_data(self, timeframe: TimeFrame, days_back: int) -> pd.DataFrame:
        if not self.symbols:
            active_assets = await self.get_active_assets()
            self.symbols = [asset['symbol'] for asset in active_assets]

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        batch_size = 1000
        all_dfs = []

        for i in range(0, len(self.symbols), batch_size):
            batch = self.symbols[i:i + batch_size]
            request = StockBarsRequest(
                symbol_or_symbols=batch,
                timeframe=timeframe,
                start=start_date,
                end=end_date
            )
            bars = self.stock_historical_data_client.get_stock_bars(request)
            all_dfs.append(bars.df)

        return pd.concat(all_dfs) if all_dfs else pd.DataFrame()

    def store_results(self, scanner_type: str, results: List[Dict]):
        """Store scanner results in MongoDB"""
        if not results:
            return
        
        timestamp = datetime.now()
        documents = [
            {
                **result,
                "scanner_type": scanner_type,
                "timestamp": timestamp,
                "timeframe": "1D" if scanner_type == "relative_volume" else "4H",
                "scan_date": timestamp.strftime("%Y-%m-%d")
            }
            for result in results
        ]
        
        try:
            collection.insert_many(documents)
            print(f"Stored {len(documents)} {scanner_type} results in MongoDB")
        except Exception as e:
            print(f"Error storing {scanner_type} results in MongoDB: {str(e)}")

    async def scan_ema_crossover(self, timeframe: TimeFrame = TimeFrame(4, TimeFrameUnit.Hour), days_back: int = 5) -> List[Dict]:
        """Scan for stocks with 9/26 EMA crossover, price $3-$8, and >3% change"""
        bars_df = await self.fetch_bar_data(timeframe, days_back)
        results = []

        print(f"Scanning {len(self.symbols)} tickers for EMA crossover...")
        for symbol in tqdm(self.symbols, desc="Processing tickers"):
            try:
                symbol_data = bars_df[bars_df.index.get_level_values('symbol') == symbol]
                if symbol_data.empty:
                    continue

                if len(symbol_data) < 2:
                    continue

                latest_bar = symbol_data.iloc[-1]
                prev_bar = symbol_data.iloc[-2]
                current_price = latest_bar['close']
                percent_change = ((latest_bar['close'] - prev_bar['close']) / prev_bar['close']) * 100

                if not (3 <= current_price <= 8) or percent_change <= 3:
                    continue

                ema_9 = self.calculate_ema(symbol_data, 9)
                ema_26 = self.calculate_ema(symbol_data, 26)

                latest_ema_9 = ema_9.iloc[-1]
                latest_ema_26 = ema_26.iloc[-1]
                prev_ema_9 = ema_9.iloc[-2]
                prev_ema_26 = ema_26.iloc[-2]

                if (prev_ema_9 <= prev_ema_26) and (latest_ema_9 > latest_ema_26):
                    results.append({
                        'symbol': symbol,
                        'price': current_price,
                        'percent_change': percent_change,
                        'ema_9': latest_ema_9,
                        'ema_26': latest_ema_26
                    })

            except Exception as e:
                print(f"Error processing {symbol}: {str(e)}")
                continue

        self.store_results("ema_crossover", results)
        return results

    async def scan_relative_volume(self) -> List[Dict]:
        """Scan for stocks with relative volume >= 2 and current volume > 100,000 using Snapshot endpoint"""
        print(f"Scanning {len(self.symbols)} tickers for Relative Volume...")
        
        if not self.symbols:
            active_assets = await self.get_active_assets()
            self.symbols = [asset['symbol'] for asset in active_assets]

        request = StockSnapshotRequest(symbol_or_symbols=self.symbols, feed=DataFeed.IEX)
        snapshots = self.stock_historical_data_client.get_stock_snapshot(request)
        
        results = []

        for symbol in tqdm(self.symbols, desc="Processing tickers"):
            try:
                snapshot = snapshots.get(symbol)
                if not snapshot or not snapshot.daily_bar:
                    continue

                current_volume = snapshot.daily_bar.volume
                if current_volume <= 100000:  # Note: You had 100,000 here, not 10,000
                    continue

                close_price = snapshot.daily_bar.close
                if close_price <= 2 or close_price >= 9:
                    continue

                prev_volume = getattr(snapshot, 'previous_daily_bar', None)
                if prev_volume is None:
                    continue
                prev_volume = prev_volume.volume

                current_price = snapshot.latest_trade.price if snapshot.latest_trade else snapshot.daily_bar.close

                if prev_volume == 0:
                    continue
                relative_volume = current_volume / prev_volume

                if relative_volume >= 2:
                    results.append({
                        'symbol': symbol,
                        'price': current_price,
                        'current_volume': current_volume,
                        'prev_volume': prev_volume,
                        'relative_volume': relative_volume
                    })

            except Exception as e:
                print(f"Error processing {symbol}: {str(e)}")
                continue

        self.store_results("relative_volume", results)
        return results

    async def run(self, scan_interval: int = 300):
        """Run multiple scanners continuously with sorted results"""
        while True:
            try:
                print(f"Starting stock scan at {datetime.now()}")
                
                # EMA Crossover Scan
                ema_results = await self.scan_ema_crossover()
                if ema_results:
                    # Sort by percent_change, highest to lowest
                    ema_results = sorted(ema_results, key=lambda x: x['percent_change'], reverse=True)
                    print(f"EMA Crossover - Found {len(ema_results)} matches (sorted by % change):")
                    for stock in ema_results:
                        print(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, Change: {stock['percent_change']:.2f}%, EMA9: {stock['ema_9']:.2f}, EMA26: {stock['ema_26']:.2f}")

                # Relative Volume Scan
                rvol_results = await self.scan_relative_volume()
                if rvol_results:
                    # Sort by relative_volume, highest to lowest
                    rvol_results = sorted(rvol_results, key=lambda x: x['relative_volume'], reverse=True)
                    print(f"Relative Volume - Found {len(rvol_results)} matches (sorted by RVol):")
                    for stock in rvol_results:
                        print(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, RVol: {stock['relative_volume']:.2f}, Vol: {stock['current_volume']}")

                if not (ema_results or rvol_results):
                    print("No stocks matched any criteria")

            except Exception as e:
                print(f"Error in run: {str(e)}")

            print("\nWaiting for next scan...")
            await asyncio.sleep(scan_interval)

if __name__ == "__main__":
    scanner = TAScanner()
    asyncio.run(scanner.run())