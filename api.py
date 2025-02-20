# api.py
from fastapi import FastAPI
from data import get_stock_data

app = FastAPI()

@app.get("/stocks")
async def read_stocks():
    return get_stock_data()