# api.py
from fastapi import FastAPI
from data import get_stock_data

app = FastAPI(debug=True)  # Enable debug mode

@app.get("/stocks")
async def read_stocks():
    try:
        result = get_stock_data()
        return result
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise  # Re-raise to get full traceback in terminal