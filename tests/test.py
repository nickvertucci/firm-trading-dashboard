import yfinance as yf


def get_stock_gainers():
    # Get predefined screeners
    gainers = yf.screen("day_gainers")
    print(gainers)

get_stock_gainers()