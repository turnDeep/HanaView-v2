import logging
from curl_cffi.requests import Session
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NASDAQ100_WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

def debug_nasdaq_scrape():
    try:
        http_session = Session(impersonate="chrome110", headers={'Accept-Language': 'en-US,en;q=0.9'})
        logger.info(f"Scraping {NASDAQ100_WIKI_URL}...")
        response = http_session.get(NASDAQ100_WIKI_URL, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        table = soup.find('table', {'id': 'constituents'})
        if not table:
            print("Could not find constituents table.")
            return

        print("--- Table Headers ---")
        headers = [th.text.strip() for th in table.find_all('th')]
        print(headers)

        print("\n--- First 5 Tickers ---")
        tickers = []
        for row in table.find_all('tr')[1:6]:
            cols = row.find_all('td')
            if len(cols) > 1:
                company = cols[0].text.strip()
                ticker = cols[1].text.strip()
                print(f"Company: {company}, Ticker: {ticker}")
                tickers.append(ticker)

        print("\nExtracted tickers:", tickers)

    except Exception as e:
        logger.error(f"Error scraping NASDAQ page: {e}", exc_info=True)

if __name__ == '__main__':
    debug_nasdaq_scrape()
