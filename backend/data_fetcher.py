import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from curl_cffi.requests import Session
import openai

# --- Constants ---
DATA_DIR = 'data'
RAW_DATA_PATH = os.path.join(DATA_DIR, 'data_raw.json')
FINAL_DATA_PATH_PREFIX = os.path.join(DATA_DIR, 'data_')

# URLs
CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/"
MINKABU_INDICATORS_URL = "https://fx.minkabu.jp/indicators"

# Tickers
VIX_TICKER = "^VIX"
T_NOTE_TICKER = "ZN=F"

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Main Data Fetching Class ---
class MarketDataFetcher:
    def __init__(self):
        self.http_session = Session(impersonate="chrome110")
        self.data = {"market": {}}
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY environment variable not set. AI functions will be skipped.")
            self.openai_client = None
        else:
            self.openai_client = openai.OpenAI(api_key=api_key)

    # ... (rest of the fetching methods remain the same) ...
    def _fetch_yfinance_data(self, ticker_symbol, period="5d", interval="1h", resample_period='4h'):
        """Fetches and processes data from yfinance."""
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                raise ValueError("No data returned from yfinance")
            hist.index = hist.index.tz_convert('Asia/Tokyo')
            resampled_hist = hist['Close'].resample(resample_period).ohlc()
            resampled_hist = resampled_hist.dropna()
            current_price = hist['Close'][-1]
            history_list = [{"time": index.strftime('%Y-%m-%dT%H:%M:%S'), "open": round(row['open'], 2), "high": round(row['high'], 2), "low": round(row['low'], 2), "close": round(row['close'], 2)} for index, row in resampled_hist.iterrows()]
            return {"current": round(current_price, 2), "history": history_list}
        except Exception as e:
            logger.error(f"Error fetching {ticker_symbol}: {e}")
            return {"current": None, "history": [], "error": str(e)}

    def fetch_vix(self):
        logger.info("Fetching VIX data...")
        self.data['market']['vix'] = self._fetch_yfinance_data(VIX_TICKER, interval="1d", resample_period='1d')

    def fetch_t_note_future(self):
        logger.info("Fetching T-note future data...")
        self.data['market']['t_note_future'] = self._fetch_yfinance_data(T_NOTE_TICKER)

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
        logger.info("Fetching Fear & Greed Index...")
        try:
            start_date = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
            url = f"{CNN_FEAR_GREED_URL}{start_date}"
            response = self.http_session.get(url, timeout=30)
            response.raise_for_status()
            api_data = response.json()
            fg_data = api_data.get('fear_and_greed_historical', {}).get('data', [])
            if not fg_data: raise ValueError("No historical data found")
            current_value = fg_data[-1]['y']
            self.data['market']['fear_and_greed'] = {'now': round(current_value), 'previous_close': round(self._get_historical_value(fg_data, 1)), 'prev_week': round(self._get_historical_value(fg_data, 7)), 'prev_month': round(self._get_historical_value(fg_data, 30)), 'prev_year': round(self._get_historical_value(fg_data, 365)), 'category': self._get_fear_greed_category(current_value)}
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
            self.data['market']['fear_and_greed'] = {'now': None, 'error': str(e)}

    def fetch_economic_indicators(self):
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
                indicators.append({"date": cols[0].text.strip().split('（')[0], "time": cols[0].find('span').text.strip(), "country": cols[1].text.strip(), "name": cols[3].text.strip(), "importance": importance_stars, "forecast": cols[4].text.strip(), "result": cols[5].text.strip()})
            self.data['indicators'] = {"economic": indicators}
        except Exception as e:
            logger.error(f"Error fetching economic indicators: {e}")
            self.data['indicators'] = {"economic": [], "error": str(e)}

    def fetch_news(self):
        logger.info("Fetching news (placeholder)...")
        self.data['news'] = []

    # --- AI Generation ---
    def _call_openai_api(self, prompt, max_tokens=150):
        if not self.openai_client:
            return "OpenAI API key not configured. Skipping."
        try:
            logger.info(f"Calling OpenAI API with max_tokens={max_tokens}...")
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return f"Error generating text: {e}"

    def generate_ai_commentary(self):
        """Generates AI market commentary."""
        logger.info("Generating AI commentary...")
        vix = self.data.get('market', {}).get('vix', {}).get('current', 'N/A')
        t_note = self.data.get('market', {}).get('t_note_future', {}).get('current', 'N/A')
        fear_greed_data = self.data.get('market', {}).get('fear_and_greed', {})
        fear_greed_value = fear_greed_data.get('now', 'N/A')
        fear_greed_category = fear_greed_data.get('category', 'N/A')

        prompt = f"""
        以下の市場データを基に、日本の個人投資家向けに本日の米国市場の状況を150字程度で簡潔に解説してください。
        - VIX指数: {vix}
        - 米国10年債先物: {t_note}
        - Fear & Greed Index: {fear_greed_value} ({fear_greed_category})
        """
        self.data['market']['ai_commentary'] = self._call_openai_api(prompt, max_tokens=200)

    def generate_weekly_column(self):
        """Generates weekly column."""
        if datetime.now(timezone(timedelta(hours=9))).weekday() != 0: # Not Monday in JST
            self.data['column'] = {}
            return

        logger.info("Generating weekly column...")
        # For the column, we might want to use more data, but for now, we'll use the same as commentary.
        vix = self.data.get('market', {}).get('vix', {}).get('current', 'N/A')
        t_note = self.data.get('market', {}).get('t_note_future', {}).get('current', 'N/A')
        fear_greed = self.data.get('market', {}).get('fear_and_greed', {})

        prompt = f"""
        今週の米国市場の展望について、日本の個人投資家向けに300字程度のコラムを執筆してください。
        先週の市場を振り返り、今週の注目点を盛り込んでください。

        参考データ:
        - VIX指数: {vix}
        - 米国10年債先物: {t_note}
        - Fear & Greed Index: 現在値 {fear_greed.get('now', 'N/A')}, 1週間前 {fear_greed.get('prev_week', 'N/A')}
        - 今週の主な経済指標: {self.data.get('indicators', {}).get('economic', [])[:5]}
        """

        content = self._call_openai_api(prompt, max_tokens=400)
        self.data['column'] = {
            "weekly_report": {
                "title": "今週の注目ポイント (AIコラム)",
                "content": content,
                "date": datetime.now().strftime('%Y-%m-%d')
            }
        }

    # ... (Main Execution Methods remain the same) ...
    def fetch_all_data(self):
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
        logger.info("--- Starting Report Generation ---")
        if not os.path.exists(RAW_DATA_PATH):
            logger.error(f"{RAW_DATA_PATH} not found. Run fetch first.")
            return
        with open(RAW_DATA_PATH, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.generate_ai_commentary()
        self.generate_weekly_column()
        jst = timezone(timedelta(hours=9))
        self.data['date'] = datetime.now(jst).strftime('%Y-%m-%d')
        self.data['last_updated'] = datetime.now(jst).isoformat()
        final_path = f"{FINAL_DATA_PATH_PREFIX}{self.data['date']}.json"
        with open(final_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        with open(os.path.join(DATA_DIR, 'data.json'), 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logger.info(f"--- Report Generation Completed. Saved to {final_path} ---")
        return self.data

if __name__ == '__main__':
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
