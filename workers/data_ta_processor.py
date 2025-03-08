# workers/data_ta_processor.py
import asyncio
import pandas as pd
from datetime import datetime, timedelta
import os
from typing import List, Dict
import logging
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        self.task_queue = asyncio.Queue()
        self.running = False

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
            and '.' not in asset.symbol
        ]
        return filtered_assets

    async def _load_symbols(self):
        """Load symbols asynchronously with a delay to avoid blocking startup"""
        await asyncio.sleep(1)  # Brief delay to let UI render first
        start_time = datetime.now()
        try:
            active_assets = await self.get_active_assets()
            self.symbols = [asset['symbol'] for asset in active_assets]
            logger.info(f"Loaded {len(self.symbols)} active symbols in {(datetime.now() - start_time).total_seconds()}s")
        except Exception as e:
            logger.error(f"Error loading symbols: {str(e)}")
            self.symbols = []

    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Exponential Moving Average for given period"""
        return df['close'].ewm(span=period, adjust=False).mean()

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI for given period"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """Calculate MACD, signal line, and histogram"""
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> tuple:
        """Calculate Bollinger Bands"""
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, lower_band

    async def fetch_bar_data(self, timeframe: TimeFrame, days_back: int) -> pd.DataFrame:
        while not self.symbols and self.running:  # Wait for symbols if not yet loaded
            logger.info("Waiting for symbols to load before fetching bar data...")
            await asyncio.sleep(1)
        if not self.symbols:
            logger.warning("No symbols available for fetch_bar_data")
            return pd.DataFrame()

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
            try:
                bars = self.stock_historical_data_client.get_stock_bars(request)
                all_dfs.append(bars.df)
            except Exception as e:
                logger.error(f"Error fetching bar data for batch {i//batch_size}: {str(e)}")

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
                "timeframe": "1D" if scanner_type in ["relative_volume", "momentum_breakout", "volume_spike", "macd_crossover", "bollinger_squeeze"] else "4H",
                "scan_date": timestamp.strftime("%Y-%m-%d")
            }
            for result in results
        ]
        
        try:
            collection.insert_many(documents)
            logger.info(f"Stored {len(documents)} {scanner_type} results in MongoDB")
        except Exception as e:
            logger.error(f"Error storing {scanner_type} results in MongoDB: {str(e)}")

    async def scan_ema_crossover(self, timeframe: TimeFrame = TimeFrame(4, TimeFrameUnit.Hour), days_back: int = 5) -> List[Dict]:
        """Scan for stocks with 9/26 EMA crossover, price $3-$8, and >3% change"""
        bars_df = await self.fetch_bar_data(timeframe, days_back)
        results = []

        logger.info(f"Scanning {len(self.symbols)} tickers for EMA crossover...")
        for symbol in tqdm(self.symbols, desc="Processing tickers (EMA)"):
            try:
                symbol_data = bars_df[bars_df.index.get_level_values('symbol') == symbol]
                if symbol_data.empty or len(symbol_data) < 2:
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
                logger.error(f"Error processing {symbol} in EMA scan: {str(e)}")
                continue

        self.store_results("ema_crossover", results)
        return results

    async def scan_relative_volume(self) -> List[Dict]:
        """Scan for stocks with relative volume >= 2 and current volume > 100,000 using Snapshot endpoint"""
        while not self.symbols and self.running:  # Wait for symbols if not yet loaded
            logger.info("Waiting for symbols to load before scanning relative volume...")
            await asyncio.sleep(1)
        if not self.symbols:
            logger.warning("No symbols available for scan_relative_volume")
            return []

        logger.info(f"Scanning {len(self.symbols)} tickers for Relative Volume...")
        request = StockSnapshotRequest(symbol_or_symbols=self.symbols, feed=DataFeed.IEX)
        try:
            snapshots = self.stock_historical_data_client.get_stock_snapshot(request)
        except Exception as e:
            logger.error(f"Error fetching snapshots for relative volume: {str(e)}")
            return []

        results = []

        for symbol in tqdm(self.symbols, desc="Processing tickers (RVol)"):
            try:
                snapshot = snapshots.get(symbol)
                if not snapshot or not snapshot.daily_bar:
                    continue

                current_volume = snapshot.daily_bar.volume
                if current_volume <= 100000:
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
                logger.error(f"Error processing {symbol} in RVol scan: {str(e)}")
                continue

        self.store_results("relative_volume", results)
        return results

    async def scan_momentum_breakout(self, timeframe: TimeFrame = TimeFrame.Day, days_back: int = 20) -> List[Dict]:
        """Scan for stocks breaking out with high momentum"""
        bars_df = await self.fetch_bar_data(timeframe, days_back)
        results = []

        logger.info(f"Scanning {len(self.symbols)} tickers for momentum breakout...")
        for symbol in tqdm(self.symbols, desc="Processing tickers (Breakout)"):
            try:
                symbol_data = bars_df[bars_df.index.get_level_values('symbol') == symbol]
                if len(symbol_data) < days_back:
                    continue

                latest_bar = symbol_data.iloc[-1]
                current_price = latest_bar['close']
                current_volume = latest_bar['volume']

                if not (2 <= current_price <= 20) or current_volume <= 100000:
                    continue

                past_bars = symbol_data.iloc[:-1]
                highest_high = past_bars['high'].max()
                avg_volume = past_bars['volume'].mean()

                if current_price > highest_high and current_volume > avg_volume * 1.5:
                    results.append({
                        'symbol': symbol,
                        'price': current_price,
                        'volume': current_volume,
                        'highest_high': highest_high,
                        'avg_volume': avg_volume
                    })

            except Exception as e:
                logger.error(f"Error processing {symbol} in breakout scan: {str(e)}")
                continue

        self.store_results("momentum_breakout", results)
        return results

    async def scan_rsi_divergence(self, timeframe: TimeFrame = TimeFrame.Day, days_back: int = 20) -> List[Dict]:
        """Scan for RSI divergence indicating potential reversals"""
        bars_df = await self.fetch_bar_data(timeframe, days_back)
        results = []

        logger.info(f"Scanning {len(self.symbols)} tickers for RSI divergence...")
        for symbol in tqdm(self.symbols, desc="Processing tickers (RSI Div)"):
            try:
                symbol_data = bars_df[bars_df.index.get_level_values('symbol') == symbol]
                if len(symbol_data) < days_back:
                    continue

                current_price = symbol_data['close'].iloc[-1]
                if not (1 <= current_price <= 15):
                    continue

                rsi = self.calculate_rsi(symbol_data)
                latest_rsi = rsi.iloc[-1]
                prev_rsi = rsi.iloc[-2]
                latest_close = symbol_data['close'].iloc[-1]
                prev_close = symbol_data['close'].iloc[-2]

                if latest_close < prev_close and latest_rsi > prev_rsi and latest_rsi < 30:
                    results.append({
                        'symbol': symbol,
                        'price': latest_close,
                        'rsi': latest_rsi,
                        'type': 'bullish_divergence'
                    })
                elif latest_close > prev_close and latest_rsi < prev_rsi and latest_rsi > 70:
                    results.append({
                        'symbol': symbol,
                        'price': latest_close,
                        'rsi': latest_rsi,
                        'type': 'bearish_divergence'
                    })

            except Exception as e:
                logger.error(f"Error processing {symbol} in RSI divergence scan: {str(e)}")
                continue

        self.store_results("rsi_divergence", results)
        return results

    async def scan_volume_spike(self, timeframe: TimeFrame = TimeFrame.Day, days_back: int = 20) -> List[Dict]:
        """Scan for stocks with significant volume spikes"""
        bars_df = await self.fetch_bar_data(timeframe, days_back)
        results = []

        logger.info(f"Scanning {len(self.symbols)} tickers for volume spikes...")
        for symbol in tqdm(self.symbols, desc="Processing tickers (Vol Spike)"):
            try:
                symbol_data = bars_df[bars_df.index.get_level_values('symbol') == symbol]
                if len(symbol_data) < days_back:
                    continue

                latest_bar = symbol_data.iloc[-1]
                current_price = latest_bar['close']
                current_volume = latest_bar['volume']
                prev_close = symbol_data['close'].iloc[-2]
                percent_change = ((current_price - prev_close) / prev_close) * 100

                if not (5 <= current_price <= 50) or abs(percent_change) <= 5:
                    continue

                avg_volume = symbol_data['volume'].iloc[:-1].mean()
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

                if volume_ratio >= 3:
                    results.append({
                        'symbol': symbol,
                        'price': current_price,
                        'volume': current_volume,
                        'avg_volume': avg_volume,
                        'volume_ratio': volume_ratio,
                        'percent_change': percent_change
                    })

            except Exception as e:
                logger.error(f"Error processing {symbol} in volume spike scan: {str(e)}")
                continue

        self.store_results("volume_spike", results)
        return results

    async def scan_macd_crossover(self, timeframe: TimeFrame = TimeFrame.Day, days_back: int = 30) -> List[Dict]:
        """Scan for MACD crossovers"""
        bars_df = await self.fetch_bar_data(timeframe, days_back)
        results = []

        logger.info(f"Scanning {len(self.symbols)} tickers for MACD crossover...")
        for symbol in tqdm(self.symbols, desc="Processing tickers (MACD)"):
            try:
                symbol_data = bars_df[bars_df.index.get_level_values('symbol') == symbol]
                if len(symbol_data) < days_back:
                    continue

                latest_bar = symbol_data.iloc[-1]
                current_price = latest_bar['close']
                current_volume = latest_bar['volume']

                if not (2 <= current_price <= 25) or current_volume <= 50000:
                    continue

                macd, signal_line = self.calculate_macd(symbol_data)
                latest_macd = macd.iloc[-1]
                latest_signal = signal_line.iloc[-1]
                prev_macd = macd.iloc[-2]
                prev_signal = signal_line.iloc[-2]

                if prev_macd <= prev_signal and latest_macd > latest_signal:
                    results.append({
                        'symbol': symbol,
                        'price': current_price,
                        'macd': latest_macd,
                        'signal': latest_signal,
                        'type': 'bullish_crossover'
                    })
                elif prev_macd >= prev_signal and latest_macd < latest_signal:
                    results.append({
                        'symbol': symbol,
                        'price': current_price,
                        'macd': latest_macd,
                        'signal': latest_signal,
                        'type': 'bearish_crossover'
                    })

            except Exception as e:
                logger.error(f"Error processing {symbol} in MACD scan: {str(e)}")
                continue

        self.store_results("macd_crossover", results)
        return results

    async def scan_bollinger_squeeze(self, timeframe: TimeFrame = TimeFrame.Day, days_back: int = 40) -> List[Dict]:
        """Scan for Bollinger Band squeezes"""
        bars_df = await self.fetch_bar_data(timeframe, days_back)
        results = []

        logger.info(f"Scanning {len(self.symbols)} tickers for Bollinger Band squeeze...")
        for symbol in tqdm(self.symbols, desc="Processing tickers (BB Squeeze)"):
            try:
                symbol_data = bars_df[bars_df.index.get_level_values('symbol') == symbol]
                if len(symbol_data) < days_back:
                    continue

                latest_bar = symbol_data.iloc[-1]
                current_price = latest_bar['close']
                current_volume = latest_bar['volume']

                if not (3 <= current_price <= 30) or current_volume <= 75000:
                    continue

                upper_band, lower_band = self.calculate_bollinger_bands(symbol_data)
                band_width = upper_band - lower_band
                latest_width = band_width.iloc[-1]
                past_widths = band_width.iloc[-21:-1]

                if latest_width < past_widths.min():
                    results.append({
                        'symbol': symbol,
                        'price': current_price,
                        'band_width': latest_width,
                        'upper_band': upper_band.iloc[-1],
                        'lower_band': lower_band.iloc[-1]
                    })

            except Exception as e:
                logger.error(f"Error processing {symbol} in BB squeeze scan: {str(e)}")
                continue

        self.store_results("bollinger_squeeze", results)
        return results

    async def worker(self):
        """Worker coroutine to process tasks from the queue"""
        while self.running:
            try:
                scan_func = await self.task_queue.get()
                logger.info(f"Starting task: {scan_func.__name__} at {datetime.now()}")

                results = await scan_func()
                if results:
                    if scan_func.__name__ == "scan_ema_crossover":
                        results = sorted(results, key=lambda x: x['percent_change'], reverse=True)
                        logger.info(f"EMA Crossover - Found {len(results)} matches (sorted by % change):")
                        for stock in results[:5]:
                            logger.info(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, "
                                       f"Change: {stock['percent_change']:.2f}%, EMA9: {stock['ema_9']:.2f}, "
                                       f"EMA26: {stock['ema_26']:.2f}")
                    elif scan_func.__name__ == "scan_relative_volume":
                        results = sorted(results, key=lambda x: x['relative_volume'], reverse=True)
                        logger.info(f"Relative Volume - Found {len(results)} matches (sorted by RVol):")
                        for stock in results[:5]:
                            logger.info(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, "
                                       f"RVol: {stock['relative_volume']:.2f}, Vol: {stock['current_volume']}")
                    elif scan_func.__name__ == "scan_momentum_breakout":
                        results = sorted(results, key=lambda x: x['price'] - x['highest_high'], reverse=True)
                        logger.info(f"Momentum Breakout - Found {len(results)} matches (sorted by breakout strength):")
                        for stock in results[:5]:
                            logger.info(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, "
                                       f"Vol: {stock['volume']}, High: {stock['highest_high']:.2f}")
                    elif scan_func.__name__ == "scan_rsi_divergence":
                        results = sorted(results, key=lambda x: x['rsi'], reverse=True)
                        logger.info(f"RSI Divergence - Found {len(results)} matches (sorted by RSI):")
                        for stock in results[:5]:
                            logger.info(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, "
                                       f"RSI: {stock['rsi']:.2f}, Type: {stock['type']}")
                    elif scan_func.__name__ == "scan_volume_spike":
                        results = sorted(results, key=lambda x: x['volume_ratio'], reverse=True)
                        logger.info(f"Volume Spike - Found {len(results)} matches (sorted by Vol Ratio):")
                        for stock in results[:5]:
                            logger.info(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, "
                                       f"Vol Ratio: {stock['volume_ratio']:.2f}, Change: {stock['percent_change']:.2f}%")
                    elif scan_func.__name__ == "scan_macd_crossover":
                        results = sorted(results, key=lambda x: abs(x['macd'] - x['signal']), reverse=True)
                        logger.info(f"MACD Crossover - Found {len(results)} matches (sorted by MACD strength):")
                        for stock in results[:5]:
                            logger.info(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, "
                                       f"MACD: {stock['macd']:.2f}, Signal: {stock['signal']:.2f}, Type: {stock['type']}")
                    elif scan_func.__name__ == "scan_bollinger_squeeze":
                        results = sorted(results, key=lambda x: x['band_width'])
                        logger.info(f"Bollinger Squeeze - Found {len(results)} matches (sorted by band width):")
                        for stock in results[:5]:
                            logger.info(f"Symbol: {stock['symbol']}, Price: ${stock['price']:.2f}, "
                                       f"Width: {stock['band_width']:.2f}, Upper: {stock['upper_band']:.2f}")
                else:
                    logger.info(f"{scan_func.__name__} - No stocks matched criteria")

                self.task_queue.task_done()
            except Exception as e:
                logger.error(f"Worker error: {str(e)}")
                self.task_queue.task_done()  # Ensure task is marked done even on error

    async def scheduler(self, scan_interval: int = 300):
        """Schedule scans by adding them to the task queue"""
        # Wait for symbols to be loaded before starting scans
        while not self.symbols and self.running:
            logger.info("Waiting for symbols to load before scheduling scans...")
            await asyncio.sleep(1)
        if not self.running:
            return

        while self.running:
            logger.info(f"Scheduling scans at {datetime.now()}")
            await self.task_queue.put(self.scan_ema_crossover)
            await self.task_queue.put(self.scan_relative_volume)
            await self.task_queue.put(self.scan_momentum_breakout)
            await self.task_queue.put(self.scan_rsi_divergence)
            await self.task_queue.put(self.scan_volume_spike)
            await self.task_queue.put(self.scan_macd_crossover)
            await self.task_queue.put(self.scan_bollinger_squeeze)
            logger.info(f"Queue size: {self.task_queue.qsize()}")
            await asyncio.sleep(scan_interval)

    async def run(self, scan_interval: int = 300, num_workers: int = 1):
        """Run the scanner with a task queue in the background"""
        self.running = True
        logger.info("Starting TA scanner")
        try:
            # Start loading symbols in the background
            asyncio.create_task(self._load_symbols())
            # Start workers and scheduler
            workers = [asyncio.create_task(self.worker()) for _ in range(num_workers)]
            scheduler = asyncio.create_task(self.scheduler(scan_interval))
            await asyncio.gather(scheduler, *workers)
        except asyncio.CancelledError:
            self.running = False
            for task in asyncio.all_tasks():
                task.cancel()
            await asyncio.gather(*asyncio.all_tasks(), return_exceptions=True)
            logger.info("Scanner shut down gracefully")
        except Exception as e:
            logger.error(f"Run error: {str(e)}")
            self.running = False

if __name__ == "__main__":
    scanner = TAScanner()
    asyncio.run(scanner.run(scan_interval=300, num_workers=4))