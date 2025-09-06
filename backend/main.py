# This file will contain the FastAPI application.
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import json
from datetime import datetime
import os
import re

app = FastAPI()

DATA_DIR = 'data'

def get_latest_data_file():
    """
    Finds the latest data_YYYY-MM-DD.json file in the DATA_DIR.
    """
    if not os.path.isdir(DATA_DIR):
        return None

    files = os.listdir(DATA_DIR)
    data_files = []
    # Regex to match the dated file format
    file_pattern = re.compile(r'^data_(\d{4}-\d{2}-\d{2})\.json$')

    for f in files:
        match = file_pattern.match(f)
        if match:
            data_files.append(f)

    if not data_files:
        # Fallback to data.json if no dated files are found
        fallback_path = os.path.join(DATA_DIR, 'data.json')
        if os.path.exists(fallback_path):
            return fallback_path
        return None

    # Sort files by date (newest first) and return the latest one
    latest_file = sorted(data_files, reverse=True)[0]
    return os.path.join(DATA_DIR, latest_file)

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
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
