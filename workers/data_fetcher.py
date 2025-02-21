import asyncio

async def fetch_trading_data():
    while True:
        print("Fetching market data...")
        await asyncio.sleep(5)  # Simulate API call