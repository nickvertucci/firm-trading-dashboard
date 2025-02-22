# api.py
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
import yfinance as yf
from yfinance import EquityQuery
import pymongo
from dotenv import load_dotenv
import os
from datetime import datetime
from components.watchlist_card import Watchlist
import logging

app = FastAPI(debug=True)  # Enable debug mode

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

# MongoDB connection setup (moved from data.py)
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
db = client["trading_db"]
collection_stock_prices = db["stock_prices"]
collection_stock_info_details = db["stock_info_details"]

@app.get("/get_stock_ohlcv_data")
async def get_stock_ohlcv_data():
    """Fetch OHLCV stock data from MongoDB for watchlist tickers"""
    try:
        # Initialize watchlist
        watchlist = Watchlist()
        tickers = [item["ticker"] for item in watchlist.watchlist_items]
        
        if not tickers:  # If watchlist is empty, return empty list
            logger.info("No tickers in watchlist, returning empty result")
            return []
        
        # Fetch all data for today from MongoDB for watchlist tickers
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        query_filter = {
            "timestamp": {"$gte": today},
            "ticker": {"$in": tickers}
        }
                
        cursor = collection_stock_prices.find(query_filter).sort("timestamp", pymongo.ASCENDING)
        
        result = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        
        logger.info(f"Returning {len(result)} OHLCV records for {len(tickers)} tickers")
        return result
    
    except Exception as e:
        logger.error(f"API Error in /get_stock_ohlcv_data: {str(e)}", exc_info=True)
        raise

@app.get("/get_stock_info_data")
async def get_stock_info_data():
    """Fetch INFO stock data from MongoDB for watchlist tickers"""
    try:
        # Initialize watchlist
        watchlist = Watchlist()
        tickers = [item["ticker"] for item in watchlist.watchlist_items]
        
        if not tickers:  # If watchlist is empty, return empty list
            logger.info("No tickers in watchlist, returning empty result")
            return []
        
        # Fetch all data for today from MongoDB for watchlist tickers
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        query_filter = {
            "timestamp": {"$gte": today},
            "ticker": {"$in": tickers}
        }
                
        cursor = collection_stock_info_details.find(query_filter).sort("timestamp", pymongo.ASCENDING)
        
        result = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        
        logger.info(f"Returning {len(result)} INFO records for {len(tickers)} tickers")
        return result
    
    except Exception as e:
        logger.error(f"API Error in /get_stock_info_data: {str(e)}", exc_info=True)
        raise

@app.get("/gainers")
async def read_day_gainers():
    """Fetch raw day gainers data from Yahoo Finance using yf.screen('day_gainers')"""
    try:
        # Fetch "Day Gainers" predefined screen directly from yfinance
        gainers_data = yf.screen("day_gainers")
        
        logger.info("Returning raw day gainers data from Yahoo Finance")
        return gainers_data
    
    except Exception as e:
        logger.error(f"API Error in /gainers: {str(e)}", exc_info=True)
        raise

@app.get("/most_actives")
async def read_most_actives():
    """Fetch raw day gainers data from Yahoo Finance using yf.screen('most_actives')"""
    try:
        # Fetch "Day Gainers" predefined screen directly from yfinance
        gainers_data = yf.screen("most_actives")
        
        logger.info("Returning raw day most actives data from Yahoo Finance")
        return gainers_data
    
    except Exception as e:
        logger.error(f"API Error in /most_actives: {str(e)}", exc_info=True)
        raise

@app.get("/small_cap_gainers")
async def read_small_cap_gainers(
    fields: str = Query(None, description="Comma-separated list of fields to return (e.g., 'displayName,symbol')")
):
    """Fetch raw day gainers data from Yahoo Finance using yf.screen('small_cap_gainers')"""
    try:
        # Fetch "Day Gainers" predefined screen directly from yfinance
        gainers_data = yf.screen("small_cap_gainers")
        
        # If fields parameter is provided, filter the response
        if fields:
            requested_fields = [field.strip() for field in fields.split(",")]
            # Filter each quote to include only the requested fields
            filtered_quotes = [
                {key: quote[key] for key in requested_fields if key in quote}
                for quote in gainers_data["quotes"]
            ]
            gainers_data["quotes"] = filtered_quotes
        
        logger.info("Returning raw day small cap gainers data from Yahoo Finance")
        return gainers_data
    
    except Exception as e:
        logger.error(f"API Error in /small_cap_gainers: {str(e)}", exc_info=True)
        raise

@app.get("/firm_gainers")
async def read_firm_gainers(
    fields: str = Query(None, description="Comma-separated list of fields to return (e.g., 'displayName,symbol')")
):
    """Fetch custom firm gainers data from Yahoo Finance using a custom EquityQuery"""
    try:
        # Define custom query for "firm_gainers"
        q = EquityQuery('and', [
            EquityQuery('gt', ['percentchange', 3]),
            EquityQuery('eq', ['region', 'us']),
            EquityQuery('gte', ['intradaymarketcap', 20000000]),  # 20M market cap
            EquityQuery('gte', ['intradayprice', 0.6]),           # Price >= $0.60
            EquityQuery('gt', ['dayvolume', 15000])               # Volume > 15,000
        ])
        
        # Fetch data with the custom query, sorted by percent change descending
        firm_gainers_data = yf.screen(q, sortField='percentchange', sortAsc=False)
        
        # If fields parameter is provided, filter the response
        if fields:
            requested_fields = [field.strip() for field in fields.split(",")]
            # Filter each quote to include only the requested fields
            filtered_quotes = [
                {key: quote[key] for key in requested_fields if key in quote}
                for quote in firm_gainers_data["quotes"]
            ]
            firm_gainers_data["quotes"] = filtered_quotes
        
        logger.info("Returning firm gainers data from Yahoo Finance")
        return firm_gainers_data
    
    except Exception as e:
        logger.error(f"API Error in /firm_gainers: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)