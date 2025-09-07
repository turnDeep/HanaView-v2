import json
import logging
import logging.handlers
import os
import re
import sys
from datetime import datetime, timedelta, timezone
import time
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from curl_cffi.requests import Session
import openai
import httpx
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Constants ---
DATA_DIR = 'data'
RAW_DATA_PATH = os.path.join(DATA_DIR, 'data_raw.json')
FINAL_DATA_PATH_PREFIX = os.path.join(DATA_DIR, 'data_')

# URLs
CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/"
YAHOO_FINANCE_NEWS_URL = "https://finance.yahoo.com/topic/stock-market-news/"
YAHOO_EARNINGS_CALENDAR_URL = "https://finance.yahoo.com/calendar/earnings"
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

# Monex URLs
MONEX_ECONOMIC_CALENDAR_URL = "https://mst.monex.co.jp/pc/servlet/ITS/report/EconomyIndexCalendar"
MONEX_US_EARNINGS_URL = "https://mst.monex.co.jp/mst/servlet/ITS/fi/FIClosingCalendarUSGuest"
MONEX_JP_EARNINGS_URL = "https://mst.monex.co.jp/mst/servlet/ITS/fi/FIClosingCalendarJPGuest"

# Tickers
VIX_TICKER = "^VIX"
T_NOTE_TICKER = "ZN=F"

# Important tickers from originalcalendar.py
US_TICKER_LIST = ["AAPL", "NVDA", "MSFT", "GOOG", "META", "AMZN", "NFLX", "BRK-B", "TSLA", "AVGO", 
                  "LLY", "WMT", "JPM", "V", "UNH", "XOM", "ORCL", "MA", "HD", "PG", "COST", "JNJ", 
                  "ABBV", "TMUS", "BAC", "CRM", "KO", "CVX", "VZ", "MRK", "AMD", "PEP", "CSCO", 
                  "LIN", "ACN", "WFC", "TMO", "ADBE", "MCD", "ABT", "BX", "PM", "NOW", "IBM", "AXP", 
                  "MS", "TXN", "GE", "QCOM", "CAT", "ISRG", "DHR", "INTU", "DIS", "CMCSA", "AMGN", 
                  "T", "GS", "PFE", "NEE", "CHTR", "RTX", "BKNG", "UBER", "AMAT", "SPGI", "LOW", 
                  "BLK", "PGR", "UNP", "SYK", "HON", "ETN", "SCHW", "LMT", "TJX", "COP", "ANET", 
                  "BSX", "KKR", "VRTX", "C", "PANW", "ADP", "NKE", "BA", "MDT", "FI", "UPS", "SBUX", 
                  "ADI", "CB", "GILD", "MU", "BMY", "DE", "PLD", "MMC", "INTC", "AMT", "SO", "LRCX", 
                  "ELV", "DELL", "PLTR", "REGN", "MDLZ", "MO", "HCA", "SHW", "KLAC", "ICE", "CI", "ABNB"]

JP_TICKER_LIST = ["7203", "8306", "6501", "6861", "6758", "9983", "6098", "9984", "8316", "9432", 
                  "4519", "4063", "8058", "8001", "8766", "8035", "9433", "8031", "7974", "4568", 
                  "9434", "8411", "2914", "7267", "7741", "7011", "4502", "6857", "6902", "4661", 
                  "6503", "3382", "6367", "8725", "4578", "6702", "6981", "6146", "7751", "6178", 
                  "4543", "4901", "6273", "8053", "8002", "6954", "5108", "8591", "6301", "8801", 
                  "6723", "8750", "6762", "6594", "9020", "6701", "9613", "4503", "8267", "8630", 
                  "6752", "6201", "9022", "7733", "4452", "4689", "2802", "5401", "1925", "7269", 
                  "8802", "8113", "2502", "8015", "4612", "4307", "1605", "8309", "8308", "1928", 
                  "8604", "9101", "6326", "4684", "7532", "9735", "8830", "9503", "5020", "3659", 
                  "9843", "6971", "7832", "4091", "7309", "4755", "9104", "4716", "7936", "9766", 
                  "4507", "8697", "5802", "2503", "7270", "6920", "6869", "6988", "2801", "2587", 
                  "3407", "5803", "7201", "8593", "9531", "4523", "9107", "7202", "3092", "8601", 
                  "5019", "9202", "9435", "1802", "4768", "7911", "4151", "9502", "6586", "7701", 
                  "3402", "7272", "9532", "9697", "4911", "9021", "8795", "3064", "7259", "1812", 
                  "2897", "7912", "4324", "6504", "7013", "7550", "6645", "5713", "5411", "4188"]

# --- Error Handling ---
class MarketDataError(Exception):
    """Custom exception for data fetching and processing errors."""
    def __init__(self, code, message=None):
        self.code = code
        self.message = message or ERROR_CODES.get(code, "An unknown error occurred.")
        super().__init__(f"[{self.code}] {self.message}")

ERROR_CODES = {
    "E001": "OpenAI API key is not configured.",
    "E002": "Data file could not be read.",
    "E003": "Failed to connect to an external API.",
    "E004": "Failed to fetch Fear & Greed Index data.",
    "E005": "AI content generation failed.",
    "E006": "Failed to fetch heatmap data.",
    "E007": "Failed to fetch calendar data via Selenium.",
}

# --- Logging Configuration ---
LOG_DIR = 'logs'
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

# Create a stream handler for console output
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

# Create a formatter and set it for both handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(formatter)

# Get the root logger and add handlers
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Avoid adding handlers multiple times if this module is reloaded
if not logger.handlers:
    logger.addHandler(stream_handler)


# --- Main Data Fetching Class ---
class MarketDataFetcher:
    def __init__(self):
        # curl_cffiのSessionを使用してブラウザを偽装
        self.http_session = Session(impersonate="chrome110", headers={'Accept-Language': 'en-US,en;q=0.9'})
        # yfinance用のセッションも別途作成
        self.yf_session = Session(impersonate="safari15_5")
        self.data = {"market": {}, "news": [], "indicators": {"economic": [], "us_earnings": [], "jp_earnings": []}}
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning(f"[E001] {ERROR_CODES['E001']} AI functions will be skipped.")
            self.openai_client = None
        else:
            http_client = httpx.Client(trust_env=False)
            self.openai_client = openai.OpenAI(api_key=api_key, http_client=http_client)
        
        # Setup Selenium driver
        self.driver = None

    def _setup_selenium_driver(self):
        """Setup Chrome driver for Selenium."""
        if self.driver:
            return
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=800,1080')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Selenium Chrome driver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            raise MarketDataError("E007", f"Chrome driver initialization failed: {e}")

    def _close_selenium_driver(self):
        """Close Selenium driver."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("Selenium Chrome driver closed")
            except Exception as e:
                logger.error(f"Error closing Chrome driver: {e}")

    # --- Ticker List Fetching ---
    def _get_sp500_tickers(self):
        logger.info("Fetching S&P 500 ticker list from Wikipedia...")
        try:
            response = self.http_session.get(SP500_WIKI_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'id': 'constituents'})
            tickers = [row.find_all('td')[0].text.strip() for row in table.find_all('tr')[1:]]
            return [t.replace('.', '-') for t in tickers]
        except Exception as e:
            logger.error(f"Failed to get S&P 500 tickers: {e}")
            return []

    def _get_nasdaq100_tickers(self):
        logger.info("Fetching NASDAQ 100 ticker list from Wikipedia...")
        try:
            response = self.http_session.get(NASDAQ100_WIKI_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'id': 'constituents'})
            tickers = [row.find_all('td')[0].text.strip() for row in table.find_all('tr')[1:] if len(row.find_all('td')) > 0]
            return [t.replace('.', '-') for t in tickers]
        except Exception as e:
            logger.error(f"Failed to get NASDAQ 100 tickers: {e}")
            return []

    # --- Data Fetching Methods ---
    def _fetch_yfinance_data(self, ticker_symbol, period="5d", interval="1h", resample_period='4h'):
        """Yahoo Finance API対策を含むデータ取得"""
        try:
            ticker = yf.Ticker(ticker_symbol, session=self.yf_session)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                raise ValueError("No data returned")

            hist.index = hist.index.tz_convert('Asia/Tokyo')
            resampled_hist = hist['Close'].resample(resample_period).ohlc().dropna()
            current_price = hist['Close'].iloc[-1]
            history_list = [
                {
                    "time": index.strftime('%Y-%m-%dT%H:%M:%S'),
                    "open": round(row['open'], 2),
                    "high": round(row['high'], 2),
                    "low": round(row['low'], 2),
                    "close": round(row['close'], 2)
                } for index, row in resampled_hist.iterrows()
            ]
            return {"current": round(current_price, 2), "history": history_list}
        except Exception as e:
            logger.error(f"Error fetching {ticker_symbol}: {e}")
            raise MarketDataError("E003", f"yfinance failed for {ticker_symbol}: {e}") from e

    def fetch_vix(self):
        logger.info("Fetching VIX data...")
        try:
            self.data['market']['vix'] = self._fetch_yfinance_data(VIX_TICKER)
        except MarketDataError as e:
            self.data['market']['vix'] = {"current": None, "history": [], "error": str(e)}
            logger.error(f"VIX fetch failed: {e}")

    def fetch_t_note_future(self):
        logger.info("Fetching T-note future data...")
        try:
            self.data['market']['t_note_future'] = self._fetch_yfinance_data(T_NOTE_TICKER)
        except MarketDataError as e:
            self.data['market']['t_note_future'] = {"current": None, "history": [], "error": str(e)}
            logger.error(f"T-Note fetch failed: {e}")

    def _get_historical_value(self, data, days_ago):
        target_date = datetime.now() - timedelta(days=days_ago)
        closest_item = min(data, key=lambda x: abs(datetime.fromtimestamp(x['x'] / 1000) - target_date))
        return closest_item['y'] if closest_item else None

    def _get_fear_greed_category(self, value):
        if value is None: return "Unknown"
        if value <= 25: return "Extreme Fear";
        if value <= 45: return "Fear";
        if value <= 55: return "Neutral";
        if value <= 75: return "Greed";
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
            self.data['market']['fear_and_greed'] = {'now': None, 'error': f"[E004] {ERROR_CODES['E004']}: {e}"}

    def fetch_calendar_data(self):
        """Fetch economic indicators and earnings calendar using Selenium."""
        logger.info("Fetching calendar data via Selenium...")
        
        try:
            self._setup_selenium_driver()
            dt_now = datetime.now()
            
            # Fetch economic indicators
            self._fetch_economic_indicators(dt_now)
            
            # Fetch US earnings
            self._fetch_us_earnings(dt_now)
            
            # Fetch JP earnings
            self._fetch_jp_earnings(dt_now)
            
        except Exception as e:
            logger.error(f"Error during calendar data fetching: {e}")
            self.data['indicators']['error'] = f"[E007] {ERROR_CODES['E007']}: {e}"
        finally:
            self._close_selenium_driver()

    def _fetch_economic_indicators(self, dt_now):
        """Fetch economic indicators from Monex."""
        logger.info("Fetching economic indicators from Monex...")
        try:
            self.driver.get(MONEX_ECONOMIC_CALENDAR_URL)
            time.sleep(2)
            
            # Click filters (importance level and today/tomorrow)
            try:
                # Select importance level checkbox
                importance_checkbox = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/form/table/tbody/tr[1]/td/ul/li[1]/label/input")
                importance_checkbox.click()
                time.sleep(1)
                
                # Select today and tomorrow
                today_checkbox = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/form/table/tbody/tr[2]/td/ul/li[3]/label/input")
                today_checkbox.click()
                time.sleep(1)
                
                # Click search button
                search_button = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/div[3]/a")
                search_button.click()
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Could not set filters for economic indicators: {e}")
            
            # Get table data
            table = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/div[4]/table")
            html = table.get_attribute('outerHTML')
            df = pd.read_html(html)[0]
            
            indicators = []
            for i in range(len(df)):
                try:
                    # Parse time
                    time_str = df.iloc[i, 1] if len(str(df.iloc[i, 1])) >= 5 else "00:00"
                    text0 = str(dt_now.year) + "/" + df.iloc[i, 0][:5] + " " + time_str[:5]
                    tdatetime = datetime.strptime(text0, '%Y/%m/%d %H:%M')
                    
                    # Filter by time range (past 2 hours to next 26 hours)
                    if tdatetime > dt_now - timedelta(hours=2) and tdatetime < dt_now + timedelta(hours=26):
                        indicator = {
                            "datetime": tdatetime.strftime('%m/%d %H:%M'),
                            "country": df.iloc[i, 2],
                            "name": df.iloc[i, 4][:30] if len(df.iloc[i, 4]) > 30 else df.iloc[i, 4],
                            "importance": "★★" if "★★" in str(df.iloc[i, 3]) else "★",
                            "type": "economic"
                        }
                        indicators.append(indicator)
                except Exception as e:
                    logger.debug(f"Skipping row {i} in economic indicators: {e}")
                    continue
            
            # Try to get next day's data
            try:
                next_button = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/div[4]/div[1]/span[3]")
                next_button.click()
                time.sleep(2)
                
                table = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/div[4]/table")
                html = table.get_attribute('outerHTML')
                df = pd.read_html(html)[0]
                
                for i in range(len(df)):
                    try:
                        time_str = df.iloc[i, 1] if len(str(df.iloc[i, 1])) >= 5 else "00:00"
                        text0 = str(dt_now.year) + "/" + df.iloc[i, 0][:5] + " " + time_str[:5]
                        tdatetime = datetime.strptime(text0, '%Y/%m/%d %H:%M')
                        
                        if tdatetime > dt_now - timedelta(hours=2) and tdatetime < dt_now + timedelta(hours=26):
                            indicator = {
                                "datetime": tdatetime.strftime('%m/%d %H:%M'),
                                "country": df.iloc[i, 2],
                                "name": df.iloc[i, 4][:30] if len(df.iloc[i, 4]) > 30 else df.iloc[i, 4],
                                "importance": "★★★" if "★★★" in str(df.iloc[i, 3]) else "★★" if "★★" in str(df.iloc[i, 3]) else "★",
                                "type": "economic"
                            }
                            indicators.append(indicator)
                    except Exception as e:
                        logger.debug(f"Skipping row {i} in next day economic indicators: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Could not get next day economic indicators: {e}")
            
            self.data['indicators']['economic'] = indicators
            logger.info(f"Fetched {len(indicators)} economic indicators")
            
        except Exception as e:
            logger.error(f"Error fetching economic indicators: {e}")
            self.data['indicators']['economic'] = []

    def _fetch_us_earnings(self, dt_now):
        """Fetch US earnings calendar from Monex."""
        logger.info("Fetching US earnings calendar from Monex...")
        try:
            self.driver.get(MONEX_US_EARNINGS_URL)
            time.sleep(2)
            
            # Click to get next page (usually shows more relevant dates)
            try:
                next_button = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/form/div[6]/div/div/div[1]/a[3]")
                next_button.click()
                time.sleep(2)
            except Exception as e:
                logger.debug(f"Could not click next button for US earnings: {e}")
            
            # Get table data
            table = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/form/div[6]/table")
            html = table.get_attribute('outerHTML')
            df = pd.read_html(html)[0]
            
            earnings = []
            for i in range(len(df)):
                try:
                    ticker = df.iloc[i, 2]
                    if ticker in US_TICKER_LIST:
                        # Parse datetime (add 13 hours for timezone conversion)
                        text0 = df.iloc[i, 0] + " " + df.iloc[i, 1][:5]
                        tdatetime = datetime.strptime(text0, '%Y/%m/%d %H:%M') + timedelta(hours=13)
                        
                        if tdatetime > dt_now - timedelta(hours=2):
                            company_name = df.iloc[i, 3][:20] if len(df.iloc[i, 3]) > 20 else df.iloc[i, 3]
                            earning = {
                                "datetime": tdatetime.strftime('%m/%d %H:%M'),
                                "ticker": ticker,
                                "company": f"({company_name})",
                                "type": "us_earnings"
                            }
                            earnings.append(earning)
                except Exception as e:
                    logger.debug(f"Skipping row {i} in US earnings: {e}")
                    continue
            
            # Add special tickers with fixed dates
            strtoday = datetime.now().strftime("%Y/%m/%d")
            strdt_now2 = dt_now.strftime('%m/%d --:--')
            
            special_tickers = {
                "2025/04/16": ("ASML", "(エーエスエムエル・ホールディングス)"),
                "2025/05/07": ("ARM", "(アーム・ホールディングス)"),
                "2025/03/12": ("PDD", "(ピンドゥオドゥオ)"),
                "2025/04/17": ("TSMC", "(台湾・セミコンダクター)"),
                "2025/03/25": ("AZN", "(アストラゼネカ)"),
                "2025/02/20": ("MELI", "(メルカドリブレ)")
            }
            
            if strtoday in special_tickers:
                ticker, company = special_tickers[strtoday]
                earning = {
                    "datetime": strdt_now2,
                    "ticker": ticker,
                    "company": company,
                    "type": "us_earnings"
                }
                earnings.append(earning)
            
            self.data['indicators']['us_earnings'] = earnings
            logger.info(f"Fetched {len(earnings)} US earnings")
            
        except Exception as e:
            logger.error(f"Error fetching US earnings: {e}")
            self.data['indicators']['us_earnings'] = []

    def _fetch_jp_earnings(self, dt_now):
        """Fetch Japanese earnings calendar from Monex."""
        logger.info("Fetching Japanese earnings calendar from Monex...")
        try:
            self.driver.get(MONEX_JP_EARNINGS_URL)
            time.sleep(2)
            
            # Click to get next page
            try:
                next_button = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/form/div[8]/div/div/div[1]/a[3]")
                next_button.click()
                time.sleep(2)
            except Exception as e:
                logger.debug(f"Could not click next button for JP earnings: {e}")
            
            # Get table data
            table = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/form/div[8]/table")
            html = table.get_attribute('outerHTML')
            df = pd.read_html(html)[0]
            
            earnings = []
            for i in range(len(df)):
                try:
                    # Extract ticker code from the company string
                    text2 = df.iloc[i, 2][-6:]
                    text3 = re.sub(r'\D', '', text2)
                    
                    if text3 in JP_TICKER_LIST:
                        text1 = df.iloc[i, 0] + " " + df.iloc[i, 1][:5]
                        text4 = df.iloc[i, 2][:-8]
                        company_name = text4[:20] if len(text4) > 20 else text4
                        
                        earning = {
                            "datetime": text1,
                            "ticker": text3,
                            "company": f"({company_name})",
                            "type": "jp_earnings"
                        }
                        earnings.append(earning)
                except Exception as e:
                    logger.debug(f"Skipping row {i} in JP earnings: {e}")
                    continue
            
            # Try to get more pages
            for page in range(7):
                try:
                    cur_url = self.driver.current_url
                    next_button = self.driver.find_element(By.CLASS_NAME, "next")
                    next_button.click()
                    time.sleep(2)
                    
                    if cur_url == self.driver.current_url:
                        break
                    
                    table = self.driver.find_element(By.XPATH, "/html/body/div[7]/div/div[3]/div[1]/form/div[8]/table")
                    html = table.get_attribute('outerHTML')
                    df = pd.read_html(html)[0]
                    
                    for i in range(len(df)):
                        try:
                            text2 = df.iloc[i, 2][-6:]
                            text3 = re.sub(r'\D', '', text2)
                            
                            if text3 in JP_TICKER_LIST:
                                text1 = df.iloc[i, 0] + " " + df.iloc[i, 1][:5]
                                text4 = df.iloc[i, 2][:-8]
                                company_name = text4[:20] if len(text4) > 20 else text4
                                
                                earning = {
                                    "datetime": text1,
                                    "ticker": text3,
                                    "company": f"({company_name})",
                                    "type": "jp_earnings"
                                }
                                earnings.append(earning)
                        except Exception as e:
                            logger.debug(f"Skipping row {i} in JP earnings page {page}: {e}")
                            continue
                except Exception as e:
                    logger.debug(f"Could not get page {page} for JP earnings: {e}")
                    break
            
            self.data['indicators']['jp_earnings'] = earnings
            logger.info(f"Fetched {len(earnings)} Japanese earnings")
            
        except Exception as e:
            logger.error(f"Error fetching Japanese earnings: {e}")
            self.data['indicators']['jp_earnings'] = []

    def fetch_yahoo_finance_news(self):
        """Fetches news from Yahoo Finance."""
        logger.info("Fetching news from Yahoo Finance...")
        try:
            response = self.http_session.get(YAHOO_FINANCE_NEWS_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            news_items = []
            for item in soup.find_all('li', class_='js-stream-content', limit=10):
                title_tag = item.find('a')
                summary_tag = item.find('p')

                if title_tag and summary_tag:
                    title = title_tag.get_text(strip=True)
                    link = title_tag['href']
                    if not link.startswith('http'):
                        link = f"https://finance.yahoo.com{link}"

                    summary = summary_tag.get_text(strip=True)

                    news_items.append({
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "publisher": "Yahoo Finance"
                    })

            self.data['news_raw'] = news_items
            logger.info(f"Fetched {len(news_items)} news items from Yahoo Finance.")

        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance news: {e}")
            self.data['news_raw'] = []

    def fetch_heatmap_data(self):
        """ヒートマップデータ取得（API対策強化版）"""
        logger.info("Fetching heatmap data...")
        try:
            sp500_tickers = self._get_sp500_tickers()
            nasdaq100_tickers = self._get_nasdaq100_tickers()
            logger.info(f"Found {len(sp500_tickers)} S&P 500 tickers and {len(nasdaq100_tickers)} NASDAQ 100 tickers.")

            self.data['sp500_heatmap'] = self._fetch_stock_performance_for_heatmap(sp500_tickers, batch_size=30)
            self.data['nasdaq_heatmap'] = self._fetch_stock_performance_for_heatmap(nasdaq100_tickers, batch_size=30)
        except Exception as e:
            logger.error(f"Error during heatmap data fetching: {e}")
            self.data['sp500_heatmap'] = {"stocks": [], "error": f"[E006] {ERROR_CODES['E006']}: {e}"}
            self.data['nasdaq_heatmap'] = {"stocks": [], "error": f"[E006] {ERROR_CODES['E006']}: {e}"}

    def _fetch_stock_performance_for_heatmap(self, tickers, batch_size=30):
        """改善版：レート制限対策を含むヒートマップ用データ取得（業種・フラット構造対応）"""
        if not tickers:
            return {"stocks": [], "error": "Ticker list is empty."}

        stocks = []

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]

            for ticker_symbol in batch:
                try:
                    ticker_obj = yf.Ticker(ticker_symbol, session=self.yf_session)
                    info = ticker_obj.info
                    hist = ticker_obj.history(period="2d")

                    performance = 0.0
                    if len(hist) >= 2 and hist['Close'].iloc[-2] != 0:
                        performance = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100

                    sector = info.get('sector', 'N/A')
                    industry = info.get('industry', 'N/A')
                    market_cap = info.get('marketCap', 0)

                    if sector == 'N/A' or industry == 'N/A' or market_cap == 0:
                        logger.warning(f"Skipping {ticker_symbol} due to missing sector, industry, or market cap.")
                        continue

                    stocks.append({
                        "ticker": ticker_symbol,
                        "sector": sector,
                        "industry": industry,
                        "performance": round(performance, 2),
                        "market_cap": market_cap
                    })

                except Exception as e:
                    logger.error(f"Could not fetch data for {ticker_symbol}: {e}")
                    time.sleep(0.5)
                    continue

            if i + batch_size < len(tickers):
                logger.info(f"Processed {min(i + batch_size, len(tickers))}/{len(tickers)} tickers, waiting...")
                time.sleep(3)

        return {"stocks": stocks}

    # --- AI Generation ---
    def _call_openai_api(self, prompt, json_mode=False, max_tokens=150):
        if not self.openai_client:
            raise MarketDataError("E005", "OpenAI client is not available.")
        try:
            logger.info(f"Calling OpenAI API (json_mode={json_mode}, max_tokens={max_tokens})...")
            messages = [{"role": "user", "content": prompt}]
            response_format = {"type": "json_object"} if json_mode else {"type": "text"}

            response = self.openai_client.chat.completions.create(
                model="gpt-5-mini",
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                response_format=response_format
            )
            content = response.choices[0].message.content.strip()
            return json.loads(content) if json_mode else content
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            raise MarketDataError("E005", str(e)) from e

    def generate_ai_commentary(self):
        logger.info("Generating AI commentary...")
        vix = self.data.get('market', {}).get('vix', {}).get('current', 'N/A')
        t_note = self.data.get('market', {}).get('t_note_future', {}).get('current', 'N/A')
        fear_greed_data = self.data.get('market', {}).get('fear_and_greed', {})
        fear_greed_value = fear_greed_data.get('now', 'N/A')
        fear_greed_category = fear_greed_data.get('category', 'N/A')
        prompt = f"以下の市場データを基に、日本の個人投資家向けに本日の米国市場の状況を150字程度で簡潔に解説してください。\n- VIX指数: {vix}\n- 米国10年債先物: {t_note}\n- Fear & Greed Index: {fear_greed_value} ({fear_greed_category})"
        self.data['market']['ai_commentary'] = self._call_openai_api(prompt, max_tokens=200)

    def generate_ai_news(self):
        """Generates AI news summary and topics based on fetched Yahoo Finance news."""
        logger.info("Generating AI news analysis...")

        raw_news = self.data.get('news_raw')
        if not raw_news:
            logger.warning("No raw news available to generate AI news.")
            self.data['news'] = {
                "summary": "ニュースが取得できなかったため、AIによる分析は行えませんでした。",
                "topics": [],
            }
            return

        news_content = ""
        for i, item in enumerate(raw_news):
            news_content += f"記事{i+1}: {item['title']}\n概要: {item['summary']}\n\n"

        prompt = f"""
        以下の米国市場に関するニュース記事群を分析し、日本の個人投資家向けに要約してください。

        ニュース記事:
        ---
        {news_content}
        ---

        上記のニュース全体から、今日の市場のムードが最も伝わるように、事実とその解釈を織り交ぜて「今朝の3行サマリー」を作成してください。
        さらに、最も重要と思われる「主要トピック」を3つ選び、それぞれ以下の形式で記述してください。
        - 事実: ニュースで報道された客観的な事実。
        - 解釈: その事実が市場でどのように受け止められているか、専門家としてのあなたの解釈。
        - 市場への影響: このトピックが今後の市場（特にS&P 500やNASDAQ）に与えうる短期的な影響。

        以下のJSON形式で、厳密に出力してください。

        {{
          "summary": "（ここに3行のサマリーを記述）",
          "topics": [
            {{
              "title": "（トピック1のタイトル、15文字以内）",
              "fact": "（事実を記述）",
              "interpretation": "（解釈を記述）",
              "impact": "（市場への影響を記述）"
            }},
            {{
              "title": "（トピック2のタイトル、15文字以内）",
              "fact": "（事実を記述）",
              "interpretation": "（解釈を記述）",
              "impact": "（市場への影響を記述）"
            }},
            {{
              "title": "（トピック3のタイトル、15文字以内）",
              "fact": "（事実を記述）",
              "interpretation": "（解釈を記述）",
              "impact": "（市場への影響を記述）"
            }}
          ]
        }}
        """

        news_data = self._call_openai_api(prompt, json_mode=True, max_tokens=1024)

        if isinstance(news_data, str) or 'error' in news_data:
            self.data['news'] = {
                "summary": "AIによるニュースの分析に失敗しました。",
                "topics": [],
                "error": str(news_data)
            }
        else:
            self.data['news'] = news_data

    def generate_weekly_column(self):
        if datetime.now(timezone(timedelta(hours=9))).weekday() != 0:
            self.data['column'] = {}
            return
        logger.info("Generating weekly column...")
        vix = self.data.get('market', {}).get('vix', {}).get('current', 'N/A')
        t_note = self.data.get('market', {}).get('t_note_future', {}).get('current', 'N/A')
        fear_greed = self.data.get('market', {}).get('fear_and_greed', {})
        prompt = f"今週の米国市場の展望について、日本の個人投資家向けに300字程度のコラムを執筆してください。\n先週の市場を振り返り、今週の注目点を盛り込んでください。\n\n参考データ:\n- VIX指数: {vix}\n- 米国10年債先物: {t_note}\n- Fear & Greed Index: 現在値 {fear_greed.get('now', 'N/A')}, 1週間前 {fear_greed.get('prev_week', 'N/A')}\n- 今週の主な経済指標: {self.data.get('indicators', {}).get('economic', [])[:5]}"
        content = self._call_openai_api(prompt, max_tokens=400)
        self.data['column'] = {"weekly_report": {"title": "今週の注目ポイント (AIコラム)", "content": content, "date": datetime.now().strftime('%Y-%m-%d')}}

    def generate_heatmap_ai_commentary(self):
        """Generates AI commentary for heatmaps."""
        logger.info("Generating heatmap AI commentary...")
        for index_name in ['sp500_heatmap', 'nasdaq_heatmap']:
            heatmap_data = self.data.get(index_name, {})
            if not heatmap_data or not heatmap_data.get('stocks'):
                logger.warning(f"No data for {index_name}, skipping AI commentary.")
                continue

            stocks = heatmap_data['stocks']
            stocks_sorted = sorted(stocks, key=lambda x: x.get('performance', 0), reverse=True)
            top_5 = stocks_sorted[:5]
            bottom_5 = stocks_sorted[-5:]

            sector_perf = {}
            sector_count = {}
            for stock in stocks:
                sector = stock.get('sector', 'N/A')
                perf = stock.get('performance', 0)
                if sector != 'N/A':
                    sector_perf[sector] = sector_perf.get(sector, 0) + perf
                    sector_count[sector] = sector_count.get(sector, 0) + 1

            avg_sector_perf = {s: sector_perf[s] / sector_count[s] for s in sector_perf}
            sorted_sectors = sorted(avg_sector_perf.items(), key=lambda item: item[1], reverse=True)

            prompt = f"""
            以下の{index_name.replace('_heatmap', '').upper()}のヒートマップデータを分析し、市況を要約してください。
            - 上昇率トップ5銘柄: {', '.join([f"{s['ticker']} ({s['performance']:.2f}%)" for s in top_5])}
            - 下落率トップ5銘柄: {', '.join([f"{s['ticker']} ({s['performance']:.2f}%)" for s in bottom_5])}
            - パフォーマンスが良かったセクター: {', '.join([f"{s[0]} ({s[1]:.2f}%)" for s in sorted_sectors[:3]])}
            - パフォーマンスが悪かったセクター: {', '.join([f"{s[0]} ({s[1]:.2f}%)" for s in sorted_sectors[-3:]])}

            この情報に基づき、今日の{index_name.replace('_heatmap', '').upper()}市場の動向について、100字程度で簡潔な解説を生成してください。
            """
            commentary = self._call_openai_api(prompt, max_tokens=200)
            self.data[index_name]['ai_commentary'] = commentary

    def cleanup_old_data(self):
        """Deletes data files older than 7 days."""
        logger.info("Cleaning up old data files...")
        try:
            today = datetime.now()
            seven_days_ago = today - timedelta(days=7)

            for filename in os.listdir(DATA_DIR):
                match = re.match(r'data_(\d{4}-\d{2}-\d{2})\.json', filename)
                if match:
                    file_date_str = match.group(1)
                    file_date = datetime.strptime(file_date_str, '%Y-%m-%d')
                    if file_date < seven_days_ago:
                        file_path = os.path.join(DATA_DIR, filename)
                        os.remove(file_path)
                        logger.info(f"Deleted old data file: {filename}")
        except Exception as e:
            logger.error(f"Error during data cleanup: {e}")

    # --- Main Execution Methods ---
    def fetch_all_data(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        logger.info("--- Starting Raw Data Fetch ---")

        fetch_tasks = [
            self.fetch_vix,
            self.fetch_t_note_future,
            self.fetch_fear_greed_index,
            self.fetch_calendar_data,  # Changed from fetch_economic_indicators
            self.fetch_yahoo_finance_news,
            self.fetch_heatmap_data
        ]

        for task in fetch_tasks:
            try:
                task()
            except MarketDataError as e:
                logger.error(f"Failed to execute fetch task '{task.__name__}': {e}")

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

        # AI Generation Steps
        try:
            self.generate_ai_commentary()
        except MarketDataError as e:
            logger.error(f"Could not generate AI commentary: {e}")
            self.data['market']['ai_commentary'] = f"Error: {e}"

        try:
            self.generate_ai_news()
        except MarketDataError as e:
            logger.error(f"Could not generate AI news: {e}")
            self.data['news'] = {"summary": f"Error: {e}", "topics": []}

        try:
            self.generate_heatmap_ai_commentary()
        except MarketDataError as e:
            logger.error(f"Could not generate heatmap AI commentary: {e}")
            self.data['sp500_heatmap']['ai_commentary'] = f"Error: {e}"
            self.data['nasdaq_heatmap']['ai_commentary'] = f"Error: {e}"

        try:
            self.generate_weekly_column()
        except MarketDataError as e:
            logger.error(f"Could not generate weekly column: {e}")
            self.data['column'] = {}

        jst = timezone(timedelta(hours=9))
        self.data['date'] = datetime.now(jst).strftime('%Y-%m-%d')
        self.data['last_updated'] = datetime.now(jst).isoformat()
        final_path = f"{FINAL_DATA_PATH_PREFIX}{self.data['date']}.json"
        with open(final_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        with open(os.path.join(DATA_DIR, 'data.json'), 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logger.info(f"--- Report Generation Completed. Saved to {final_path} ---")

        self.cleanup_old_data()

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