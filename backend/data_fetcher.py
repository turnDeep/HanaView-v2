import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from curl_cffi.requests import Session

# --- Constants ---
# Corrected paths to be relative to the project root
DATA_DIR = 'data'
RAW_DATA_PATH = os.path.join(DATA_DIR, 'data_raw.json')
FINAL_DATA_PATH_PREFIX = os.path.join(DATA_DIR, 'data_')

# URLs
CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/"
MINKABU_INDICATORS_URL = "https://fx.minkabu.jp/indicators"

# Tickers
VIX_TICKER = "^VIX" # Corrected VIX ticker
T_NOTE_TICKER = "ZN=F"

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Main Data Fetching Class ---
class MarketDataFetcher:
    def __init__(self):
        # Use a separate session for curl-cffi, and let yfinance manage its own
        self.http_session = Session(impersonate="chrome110")
        self.data = {"market": {}}

    # --- Financial Data Fetching ---
    def _fetch_yfinance_data(self, ticker_symbol, period="5d", interval="1h", resample_period='4h'):
        """Fetches and processes data from yfinance."""
        try:
            # Removed session from yf.Ticker call
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                raise ValueError("No data returned from yfinance")

            # Resample to 4-hour intervals
            hist.index = hist.index.tz_convert('Asia/Tokyo')
            resampled_hist = hist['Close'].resample(resample_period).ohlc()
            resampled_hist = resampled_hist.dropna()

            current_price = hist['Close'][-1]

            history_list = []
            for index, row in resampled_hist.iterrows():
                history_list.append({
                    "time": index.strftime('%Y-%m-%dT%H:%M:%S'),
                    "open": round(row['open'], 2),
                    "high": round(row['high'], 2),
                    "low": round(row['low'], 2),
                    "close": round(row['close'], 2),
                })

            return {
                "current": round(current_price, 2),
                "history": history_list
            }
        except Exception as e:
            logger.error(f"Error fetching {ticker_symbol}: {e}")
            return {"current": None, "history": [], "error": str(e)}

    def fetch_vix(self):
        """Fetches VIX data."""
        logger.info("Fetching VIX data...")
        self.data['market']['vix'] = self._fetch_yfinance_data(VIX_TICKER, interval="1d", resample_period='1d')


    def fetch_t_note_future(self):
        """Fetches 10-year T-note future data."""
        logger.info("Fetching T-note future data...")
        self.data['market']['t_note_future'] = self._fetch_yfinance_data(T_NOTE_TICKER)

    # --- Fear & Greed Index ---
    def _get_historical_value(self, data, days_ago):
        target_date = datetime.now() - timedelta(days=days_ago)
        closest_item = min(data, key=lambda x: abs(datetime.fromtimestamp(x['x'] / 1000) - target_date))
        return closest_item['y'] if closest_item else None

    def _get_fear_greed_category(self, value):
        if value is None: return "Unknown"
        if value <= 25: return "Extreme Fear"
        if value <= 45: return "Fear"
        if value <= 55: return "Neutral"
        if value <= 75: return "Greed"
        return "Extreme Greed"

    def fetch_fear_greed_index(self):
        """Fetches Fear & Greed Index from CNN API."""
        logger.info("Fetching Fear & Greed Index...")
        try:
            start_date = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
            url = f"{CNN_FEAR_GREED_URL}{start_date}"
            response = self.http_session.get(url, timeout=30)
            response.raise_for_status()
            api_data = response.json()

            fg_data = api_data.get('fear_and_greed_historical', {}).get('data', [])
            if not fg_data:
                raise ValueError("No historical data found in API response")

            current_value = fg_data[-1]['y']
            prev_close = self._get_historical_value(fg_data, 1)
            week_ago = self._get_historical_value(fg_data, 7)
            month_ago = self._get_historical_value(fg_data, 30)
            year_ago = self._get_historical_value(fg_data, 365)

            self.data['market']['fear_and_greed'] = {
                'now': round(current_value),
                'previous_close': round(prev_close) if prev_close is not None else None,
                'prev_week': round(week_ago) if week_ago is not None else None,
                'prev_month': round(month_ago) if month_ago is not None else None,
                'prev_year': round(year_ago) if year_ago is not None else None,
                'category': self._get_fear_greed_category(current_value)
            }
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
            self.data['market']['fear_and_greed'] = {'now': None, 'error': str(e)}

    # --- Economic Indicators ---
    def fetch_economic_indicators(self):
        """Fetches economic indicators from Minkabu."""
        logger.info("Fetching economic indicators...")
        try:
            response = self.http_session.get(MINKABU_INDICATORS_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            indicators = []
            rows = soup.select("div.data-table.is-indicators > table > tbody > tr")

            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 6: continue

                importance_stars = len(cols[2].find_all('i', class_='icon-star_small_on'))
                if importance_stars < 3: continue

                indicators.append({
                    "date": cols[0].text.strip().split('（')[0],
                    "time": cols[0].find('span').text.strip(),
                    "country": cols[1].text.strip(),
                    "name": cols[3].text.strip(),
                    "importance": importance_stars,
                    "forecast": cols[4].text.strip(),
                    "result": cols[5].text.strip(),
                })
            self.data['indicators'] = {"economic": indicators}
        except Exception as e:
            logger.error(f"Error fetching economic indicators: {e}")
            self.data['indicators'] = {"economic": [], "error": str(e)}

    # --- News ---
    def fetch_news(self):
        """Placeholder for news fetching logic."""
        logger.info("Fetching news (placeholder)...")
        self.data['news'] = [] # Placeholder

    # --- AI Generation (Mocks) ---
    def generate_ai_commentary(self):
        """Generates AI market commentary (mock)."""
        logger.info("Generating AI commentary (mock)...")
        vix = self.data.get('market', {}).get('vix', {}).get('current', 'N/A')
        t_note = self.data.get('market', {}).get('t_note_future', {}).get('current', 'N/A')
        self.data['market']['ai_commentary'] = f"【AI解説】本日のVIXは{vix}、10年債は{t_note}です。市場は様子見ムードが広がっています。(これはモックテキストです)"

    def generate_weekly_column(self):
        """Generates weekly column (mock)."""
        logger.info("Generating weekly column (mock)...")
        if datetime.now(timezone(timedelta(hours=9))).weekday() == 0: # Monday in JST
            self.data['column'] = {
                "weekly_report": {
                    "title": "今週の注目ポイント (AIコラム)",
                    "content": "先週の市場は一進一退の展開でした。今週は主要な経済指標の発表が相次ぐため、注意が必要です。(これはモックテキストです)",
                    "date": datetime.now().strftime('%Y-%m-%d')
                }
            }
        else:
            self.data['column'] = {}

    # --- Main Execution Methods ---
    def fetch_all_data(self):
        """Main function to fetch all raw data."""
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)

        logger.info("--- Starting Raw Data Fetch ---")
        self.fetch_vix()
        self.fetch_t_note_future()
        self.fetch_fear_greed_index()
        self.fetch_economic_indicators()
        self.fetch_news()

        with open(RAW_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logger.info(f"--- Raw Data Fetch Completed. Saved to {RAW_DATA_PATH} ---")
        return self.data

    def generate_report(self):
        """Main function to generate the final report from raw data."""
        logger.info("--- Starting Report Generation ---")
        if not os.path.exists(RAW_DATA_PATH):
            logger.error(f"{RAW_DATA_PATH} not found. Run fetch first.")
            return

        with open(RAW_DATA_PATH, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.generate_ai_commentary()
        self.generate_weekly_column()

        # Add metadata
        jst = timezone(timedelta(hours=9))
        self.data['date'] = datetime.now(jst).strftime('%Y-%m-%d')
        self.data['last_updated'] = datetime.now(jst).isoformat()

        final_path = f"{FINAL_DATA_PATH_PREFIX}{self.data['date']}.json"

        with open(final_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

        # For the API, we'll also save to a consistent filename `data.json`
        with open(os.path.join(DATA_DIR, 'data.json'), 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

        logger.info(f"--- Report Generation Completed. Saved to {final_path} ---")
        return self.data


if __name__ == '__main__':
    # Change working directory to project root
    if os.path.basename(os.getcwd()) == 'backend':
        os.chdir('..')

    if len(sys.argv) > 1:
        fetcher = MarketDataFetcher()
        if sys.argv[1] == 'fetch':
            fetcher.fetch_all_data()
        elif sys.argv[1] == 'generate':
            fetcher.generate_report()
        else:
            print("Usage: python backend/data_fetcher.py [fetch|generate]")
    else:
        print("Usage: python backend/data_fetcher.py [fetch|generate]")
