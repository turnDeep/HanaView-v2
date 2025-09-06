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

# --- Constants ---
DATA_DIR = 'data'
RAW_DATA_PATH = os.path.join(DATA_DIR, 'data_raw.json')
FINAL_DATA_PATH_PREFIX = os.path.join(DATA_DIR, 'data_')

# URLs
CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/"
MINKABU_INDICATORS_URL = "https://fx.minkabu.jp/indicators"
YAHOO_FINANCE_NEWS_URL = "https://finance.yahoo.com/topic/stock-market-news/"
YAHOO_EARNINGS_CALENDAR_URL = "https://finance.yahoo.com/calendar/earnings"
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

# Tickers
VIX_TICKER = "^VIX"  # Use VIX index for intraday data (futures VX=F is delisted)
T_NOTE_TICKER = "ZN=F"

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
}

# --- Logging Configuration ---
LOG_DIR = 'logs'
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

# # Ensure log directory exists
# os.makedirs(LOG_DIR, exist_ok=True) #いったんlogディレクトリの作成をコメントアウト

# # Create a rotating file handler
# # 5MB per file, keep 5 old files
# file_handler = logging.handlers.RotatingFileHandler(
#     LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
# )
# file_handler.setLevel(logging.INFO)

# Create a stream handler for console output
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

# Create a formatter and set it for both handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Get the root logger and add handlers
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Avoid adding handlers multiple times if this module is reloaded
if not logger.handlers:
    # logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


# --- Main Data Fetching Class ---
class MarketDataFetcher:
    def __init__(self):
        # curl_cffiのSessionを使用してブラウザを偽装
        self.http_session = Session(impersonate="chrome110", headers={'Accept-Language': 'en-US,en;q=0.9'})
        # yfinance用のセッションも別途作成
        self.yf_session = Session(impersonate="safari15_5")
        self.data = {"market": {}, "news": [], "indicators": {"economic": [], "notable_earnings": []}}
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # E001: OpenAI API Key not set. This is critical for generation steps.
            # We will log a warning but allow fetching to proceed. Generation will fail later.
            logger.warning(f"[E001] {ERROR_CODES['E001']} AI functions will be skipped.")
            self.openai_client = None
        else:
            # trust_env=False to prevent httpx from using system proxy settings,
            # which seems to be the original intent of proxies={}.
            http_client = httpx.Client(trust_env=False)
            self.openai_client = openai.OpenAI(api_key=api_key, http_client=http_client)

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
            # curl_cffiのセッションを使用してyfinanceを初期化
            ticker = yf.Ticker(ticker_symbol, session=self.yf_session)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                raise ValueError("No data returned")

            hist.index = hist.index.tz_convert('Asia/Tokyo')
            resampled_hist = hist['Close'].resample(resample_period).ohlc().dropna()
            current_price = hist['Close'][-1]
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
            # E003: Failed to connect to an external API.
            raise MarketDataError("E003", f"yfinance failed for {ticker_symbol}: {e}") from e

    def fetch_vix(self):
        logger.info("Fetching VIX data...")
        try:
            # Use default 4h resampling for VIX futures
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
            self.data['indicators']['economic'] = []
            self.data['indicators']['error'] = f"[E003] {ERROR_CODES['E003']}: {e}"

    def fetch_yahoo_finance_news(self):
        """Fetches news from Yahoo Finance."""
        logger.info("Fetching news from Yahoo Finance...")
        try:
            response = self.http_session.get(YAHOO_FINANCE_NEWS_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            news_items = []
            # Find all list items that likely contain news articles
            for item in soup.find_all('li', class_='js-stream-content', limit=10):
                title_tag = item.find('a')
                summary_tag = item.find('p')

                if title_tag and summary_tag:
                    title = title_tag.get_text(strip=True)
                    link = title_tag['href']
                    # Yahoo Finance links can be relative, so make them absolute
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
            # This is not critical, so we just log it and the AI gen will handle the empty list

    def fetch_earnings_calendar(self):
        """Fetches the earnings calendar for the current day."""
        logger.info("Fetching earnings calendar from Yahoo Finance...")
        try:
            # Yahoo's calendar page is JS-heavy, so we might need to find the right API or be clever.
            # For today, we'll try scraping the main page.
            # Note: A more robust solution might involve finding an API endpoint.
            response = self.http_session.get(f"{YAHOO_EARNINGS_CALENDAR_URL}?day={datetime.now().strftime('%Y-%m-%d')}", timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            earnings_list = []
            rows = soup.find_all('tr', class_='simpTblRow')

            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    symbol = cols[0].get_text(strip=True)
                    company = cols[1].get_text(strip=True)
                    time_str = cols[2].get_text(strip=True)

                    earnings_list.append({
                        "symbol": symbol,
                        "company": company,
                        "release_time": time_str
                    })

            self.data['earnings_raw'] = earnings_list
            logger.info(f"Fetched {len(earnings_list)} earnings announcements for today.")

        except Exception as e:
            logger.error(f"Error fetching earnings calendar: {e}")
            self.data['earnings_raw'] = []
            # This is not critical, so we just log it and the AI gen will handle the empty list


    def fetch_heatmap_data(self):
        """ヒートマップデータ取得（API対策強化版）"""
        logger.info("Fetching heatmap data...")
        try:
            sp500_tickers = self._get_sp500_tickers()
            nasdaq100_tickers = self._get_nasdaq100_tickers()
            logger.info(f"Found {len(sp500_tickers)} S&P 500 tickers and {len(nasdaq100_tickers)} NASDAQ 100 tickers.")

            # バッチサイズを小さくしてレート制限を回避
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

        # バッチ処理でレート制限を回避
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]

            for ticker_symbol in batch:
                try:
                    # curl_cffiセッションを使用
                    ticker_obj = yf.Ticker(ticker_symbol, session=self.yf_session)
                    info = ticker_obj.info
                    hist = ticker_obj.history(period="2d")

                    performance = 0.0
                    if len(hist) >= 2 and hist['Close'].iloc[-2] != 0:
                        performance = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100

                    sector = info.get('sector', 'N/A')
                    industry = info.get('industry', 'N/A')
                    market_cap = info.get('marketCap', 0)

                    # セクターやインダストリーが取得できない、または時価総額が0のものはスキップ
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
                    # エラー時は少し待機
                    time.sleep(0.5)
                    continue

            # バッチ間で待機（レート制限対策）
            if i + batch_size < len(tickers):
                logger.info(f"Processed {min(i + batch_size, len(tickers))}/{len(tickers)} tickers, waiting...")
                time.sleep(3)  # 3秒待機

        return {"stocks": stocks}

    # --- AI Generation ---
    def _call_openai_api(self, prompt, json_mode=False, max_tokens=150):
        if not self.openai_client:
            # E001 is logged at startup, here we raise E005 because the generation failed.
            raise MarketDataError("E005", "OpenAI client is not available.")
        try:
            logger.info(f"Calling OpenAI API (json_mode={json_mode}, max_tokens={max_tokens})...")
            messages = [{"role": "user", "content": prompt}]
            response_format = {"type": "json_object"} if json_mode else {"type": "text"}

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                response_format=response_format
            )
            content = response.choices[0].message.content.strip()
            return json.loads(content) if json_mode else content
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            # E005: AI content generation failed.
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

        # Prepare the news content for the prompt
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

        # Use a larger max_tokens for this more complex task
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
            # Sort by performance to find top/bottom movers
            stocks_sorted = sorted(stocks, key=lambda x: x.get('performance', 0), reverse=True)
            top_5 = stocks_sorted[:5]
            bottom_5 = stocks_sorted[-5:]

            # Calculate sector performance
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

    def select_notable_earnings(self):
        """Selects notable earnings reports using AI."""
        logger.info("Selecting notable earnings reports...")

        raw_earnings = self.data.get('earnings_raw')
        if not raw_earnings:
            logger.warning("No raw earnings data to select from.")
            return

        # Prepare the earnings list for the prompt
        earnings_list_str = ", ".join([f"{e['company']} ({e['symbol']})" for e in raw_earnings])

        prompt = f"""
        以下は、本日決算発表を予定している企業の一部です。
        - {earnings_list_str}

        これらの企業の中から、日本の個人投資家が最も注目すべきだと考えられる企業を最大5社まで選んでください。
        選定理由は考慮せず、単に注目度が高いと思われる企業のリストをJSON形式で返してください。

        以下のJSON形式で、厳密に出力してください。
        {{
          "notable_earnings": [
            {{ "symbol": "...", "company": "...", "reason": "（なぜ注目されているかの簡単な理由）" }},
            {{ "symbol": "...", "company": "...", "reason": "..." }}
          ]
        }}
        """

        selected_earnings = self._call_openai_api(prompt, json_mode=True, max_tokens=512)

        if isinstance(selected_earnings, str) or 'error' in selected_earnings:
            logger.error(f"AI selection of notable earnings failed: {selected_earnings}")
        else:
            self.data['indicators']['notable_earnings'] = selected_earnings.get('notable_earnings', [])

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
            self.fetch_economic_indicators,
            self.fetch_yahoo_finance_news,
            self.fetch_earnings_calendar,
            self.fetch_heatmap_data
        ]

        for task in fetch_tasks:
            try:
                task()
            except MarketDataError as e:
                logger.error(f"Failed to execute fetch task '{task.__name__}': {e}")
                # We can decide to add error info to the data dict here if needed
                # For now, logging is sufficient as individual methods handle their data structure on error.

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

        # AI Generation Steps - wrap in try/except to allow partial report generation
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
            self.select_notable_earnings()
        except MarketDataError as e:
            logger.error(f"Could not select notable earnings: {e}")
            self.data['indicators']['notable_earnings'] = []

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

        # Clean up old files after a successful report generation
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
