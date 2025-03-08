# api.py
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
import yfinance as yf
from yfinance import EquityQuery
import pymongo
from dotenv import load_dotenv
import os
from datetime import datetime, date
from components.watchlist_card import Watchlist
import logging
from alpaca.trading.client import TradingClient
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

app = FastAPI(debug=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

# MongoDB connection setup
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
collection_stock_prices = db["stock_prices"]
collection_stock_info_details = db["stock_info_details"]
collection_stock_ta = db["stock_ta"]

# Alpaca clients setup
trading_client = TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True)
data_client = StockHistoricalDataClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"))

##############################################################################################################################

@app.get("/get_stock_ohlcv_data")
async def get_stock_ohlcv_data():
    try:
        watchlist = Watchlist()
        tickers = [item["ticker"] for item in watchlist.watchlist_items]
        if not tickers:
            return []
        
        result = []
        for ticker in tickers:
            doc = collection_stock_prices.find_one({"ticker": ticker}, sort=[("timestamp", pymongo.DESCENDING)])
            if doc:
                result.append({k: v for k, v in doc.items() if k != "_id"})
        
        return result
    
    except Exception as e:
        raise

@app.get("/get_stock_ohlcv_intraday")
async def get_stock_ohlcv_intraday():
    try:
        watchlist = Watchlist()
        tickers = [item["ticker"] for item in watchlist.watchlist_items]
        if not tickers:
            return []

        today = date.today()
        start_of_day = datetime(today.year, today.month, today.day)
        result = []
        for ticker in tickers:
            docs = list(collection_stock_prices.find({
                "ticker": ticker,
                "timestamp": {"$gte": start_of_day}
            }).sort("timestamp", pymongo.ASCENDING))
            result.extend([{k: v for k, v in doc.items() if k != "_id"} for doc in docs])
        
        return result
    
    except Exception as e:
        raise

@app.get("/get_stock_info_data")
async def get_stock_info_data():
    try:
        watchlist = Watchlist()
        tickers = [item["ticker"] for item in watchlist.watchlist_items]
        
        if not tickers:
            return []
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        query_filter = {
            "timestamp": {"$gte": today},
            "ticker": {"$in": tickers}
        }
                
        cursor = collection_stock_info_details.find(query_filter).sort("timestamp", pymongo.ASCENDING)
        result = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        
        return result
    
    except Exception as e:
        raise

@app.get("/gainers")
async def read_day_gainers():
    try:
        gainers_data = yf.screen("day_gainers", size=100)
        return gainers_data
    except Exception as e:
        raise

@app.get("/most_actives")
async def read_most_actives():
    try:
        gainers_data = yf.screen("most_actives", size=100)
        return gainers_data
    except Exception as e:
        raise

@app.get("/small_cap_gainers")
async def read_small_cap_gainers(
    fields: str = Query(None, description="Comma-separated list of fields to return (e.g., 'displayName,symbol')")
):
    try:
        gainers_data = yf.screen("small_cap_gainers", size=100)
        if fields:
            requested_fields = [field.strip() for field in fields.split(",")]
            filtered_quotes = [
                {key: quote[key] for key in requested_fields if key in quote}
                for quote in gainers_data["quotes"]
            ]
            gainers_data["quotes"] = filtered_quotes
        return gainers_data
    except Exception as e:
        raise

@app.get("/firm_gainers")
async def read_firm_gainers(
    fields: str = Query(None, description="Comma-separated list of fields to return (e.g., 'displayName,symbol')")
):
    try:
        q = EquityQuery('and', [
            EquityQuery('gt', ['percentchange', 3]),
            EquityQuery('eq', ['region', 'us']),
            EquityQuery('gte', ['intradaymarketcap', 20000000]),
            EquityQuery('gte', ['intradayprice', 0.6]),
            EquityQuery('gt', ['dayvolume', 15000])
        ])
        firm_gainers_data = yf.screen(q, sortField='percentchange', sortAsc=False, size=100)
        if fields:
            requested_fields = [field.strip() for field in fields.split(",")]
            filtered_quotes = [
                {key: quote[key] for key in requested_fields if key in quote}
                for quote in firm_gainers_data["quotes"]
            ]
            firm_gainers_data["quotes"] = filtered_quotes
        return firm_gainers_data
    except Exception as e:
        raise

@app.get("/firm_rvol_gainers")
async def read_firm_rvol_gainers(
    fields: str = Query(None, description="Comma-separated list of fields to return (e.g., 'displayName,symbol,rvol')"),
    offset: int = Query(0, ge=0, description="Starting index of results"),
    size: int = Query(25, ge=1, le=100, description="Number of results to return")
):
    try:
        q = EquityQuery('and', [
            EquityQuery('gt', ['percentchange', 3]),
            EquityQuery('eq', ['region', 'us']),
            EquityQuery('gte', ['intradaymarketcap', 2000000]),
            EquityQuery('gte', ['intradayprice', 2]),
            EquityQuery('lte', ['intradayprice', 18]),
            EquityQuery('gt', ['dayvolume', 15000])
        ])
        firm_data = yf.screen(q, sortField='percentchange', sortAsc=False, size=250)
        quotes = [quote for quote in firm_data["quotes"] if quote.get("exchange") not in ["ASE", "PNK"]]
        for quote in quotes:
            regular_volume = quote.get("regularMarketVolume", 0)
            avg_volume = quote.get("averageDailyVolume10Day", 1)
            rvol = (regular_volume / avg_volume) * 100 if avg_volume > 0 else 0
            quote["rvol"] = rvol
        sorted_quotes = sorted(quotes, key=lambda x: x["rvol"], reverse=True)
        paginated_quotes = sorted_quotes[offset:offset + size]
        if fields:
            requested_fields = [field.strip() for field in fields.split(",")]
            filtered_quotes = [
                {key: quote[key] for key in requested_fields if key in quote}
                for quote in paginated_quotes
            ]
            paginated_quotes = filtered_quotes
        response = {
            "start": offset,
            "count": len(paginated_quotes),
            "total": len(sorted_quotes),
            "quotes": paginated_quotes,
            "offset": offset,
            "size": size,
            "next_offset": offset + size if offset + size < len(sorted_quotes) else None
        }
        return response
    except Exception as e:
        raise

@app.get("/get_ta_data")
async def get_ta_data(
    scanner_type: str = Query(None, description="Filter by scanner type (e.g., 'ema_crossover', 'relative_volume')"),
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format"),
    offset: int = Query(0, ge=0, description="Starting index of results"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return")
):
    """Fetch technical analysis data from MongoDB"""
    try:
        # Build query filter
        query_filter = {}
        
        if scanner_type:
            query_filter["scanner_type"] = scanner_type
        
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                query_filter["timestamp"] = {"$gte": start_dt}
            except ValueError:
                return {"error": "Invalid start_date format. Use YYYY-MM-DD"}

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                if "timestamp" in query_filter:
                    query_filter["timestamp"]["$lte"] = end_dt
                else:
                    query_filter["timestamp"] = {"$lte": end_dt}
            except ValueError:
                return {"error": "Invalid end_date format. Use YYYY-MM-DD"}

        # Fetch total count for pagination
        total = collection_stock_ta.count_documents(query_filter)

        # Fetch paginated data
        cursor = collection_stock_ta.find(query_filter).sort("timestamp", pymongo.DESCENDING).skip(offset).limit(limit)
        results = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        # Construct response
        response = {
            "total": total,
            "count": len(results),
            "offset": offset,
            "limit": limit,
            "next_offset": offset + limit if offset + limit < total else None,
            "data": results
        }

        logger.info(f"Fetched {len(results)} TA records for scanner_type={scanner_type}, offset={offset}, limit={limit}")
        return response

    except Exception as e:
        logger.error(f"Error in get_ta_data: {str(e)}")
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)