import asyncio

async def process_trading_data():
    while True:
        print("Processing market data...")
        await asyncio.sleep(5)  # Simulate API call