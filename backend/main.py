# This file will contain the FastAPI application.
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import json
from datetime import datetime
import os

app = FastAPI()

DATA_DIR = '../data'

def get_latest_data_file():
    """Finds the latest data_YYYY-MM-DD.json file."""
    # For this implementation, we'll use a fixed name for simplicity,
    # as specified in the data_fetcher.py placeholder.
    # A real implementation would dynamically find the latest file based on date.
    return os.path.join(DATA_DIR, 'data.json')

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/api/data")
def get_market_data():
    """Endpoint to get the latest market data."""
    try:
        data_file = get_latest_data_file()
        if not os.path.exists(data_file):
            raise HTTPException(status_code=404, detail="Data file not found.")

        with open(data_file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount the frontend directory to serve static files
# This should come AFTER all API routes
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
