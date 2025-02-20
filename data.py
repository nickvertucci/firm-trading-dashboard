# data.py
import yfinance as yf
import pandas as pd
from datetime import datetime

def get_stock_data():
    stocks = ["AAPL", "GOOGL", "TSLA"]
    try:
        # Fetch 1-minute data for today
        data = yf.download(stocks, period="1d", interval="1m")["Close"]
        if data.empty:
            print("No data returned from yfinance")
            # Fallback: Return a single dummy row
            return [{"timestamp": datetime.now().isoformat(), "AAPL": 150.00, "GOOGL": 2750.00, "TSLA": 900.00}]
        
        # Convert to list of dictionaries
        result = []
        for timestamp in data.index:
            row = {"timestamp": timestamp.isoformat()}
            for stock in stocks:
                row[stock] = round(data[stock][timestamp], 2) if not pd.isna(data[stock][timestamp]) else None
            result.append(row)
        print(f"Fetched {len(result)} rows of data")
        return result
    except Exception as e:
        print(f"Error fetching data: {e}")
        # Fallback: Return dummy data
        return [{"timestamp": datetime.now().isoformat(), "AAPL": 150.00, "GOOGL": 2750.00, "TSLA": 900.00}]