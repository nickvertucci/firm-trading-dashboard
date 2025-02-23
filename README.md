# firm-trading-dashboard

# Technology Stack
- NiceGUI
- FastAPI
- MongoDB
- Asyncio

# Activating Virtual Environment
.venv\Scripts\activate  

# Testing
run the data_fetcher.py worker individually for testing
python -m workers.data_ohlcv_fetcher

# Layout
FIRM-TRADING-DASHBOARD/
├── components/                  # UI card components
│   ├── firmGainers_card.py      # Firm gainers card
│   ├── mostActivelist_card.py   # Most active stocks card
│   ├── smallCapgainers_card.py  # Small-cap gainers card
│   ├── watchlist_card.py        # Watchlist card
├── workers/                     # Worker/background task files (assuming this is the intent)
│   ├── data_info_fetcher.py     # Stock info fetcher worker
│   ├── data_ohlcv_fetcher.py    # OHLCV data fetcher worker
│   ├── data_ta_processor.py     # Technical analysis processor
├── dashboard.py                 # Dashboard page logic
├── main.py                      # Main app entry point with routing
├── api.py                       # FastAPI API routes
└── ...                          # Other files (e.g., .env, requirements.txt)