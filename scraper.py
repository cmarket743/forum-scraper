import time
import datetime
import pandas as pd
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote_plus
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import praw   # ✅ Reddit API library

# === CONFIGURATION ===
KEYWORDS = [
    "currency transfer", "international money transfer", "send money abroad",
    "send money home", "lump sum transfer", "invest a lump sum",
    "recommend an FX Transfer service", "recommend FX broker",
    "transferring house deposit abroad", "transferring lump sum abroad",
    "sending pension lump sum overseas"
]

GOOGLE_SHEET_NAME = "forum scraper"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/16OtDpKLeXUPzFM_OQerVOQrVaD6XJQ7o8DrSU0bTuGk/edit?gid=1484600113#gid=1484600113"

# === LOGGING CONFIG ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === GOOGLE SHEETS SETUP ===
def setup_google_sheets():
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not creds_json:
        raise ValueError("❌ GOOGLE_SHEETS_CREDENTIALS not found in environment variables!")

    import json
    creds_dict = json.loads(creds_json)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    logging.info("✅ Connected to Google Sheets")
    return client.open_by_url(GOOGLE_SHEET_URL).sheet1

# === REDDIT SCRAPER (API) ===
def scrape_reddit():
    logging.info("🔍 Scraping Reddit API...")
    results = []

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "forum-scraper")
    )

    for keyword in KEYWORDS:
        logging.info(f"➡ Searching Reddit for: {keyword}")
        try:
            for submission in reddit.subreddit("all").search(keyword, sort="new", time_filter="day", limit=10):
                results.append({
                    "Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Forum": "Reddit",
                    "Keyword": keyword,
                    "URL": f"https://www.reddit.com{submission.permalink}"
                })
            logging.info(f"✅ Found {len(results)} results so far from Reddit")
        except Exception as e:
            logging.error(f"❌ Error scraping Reddit for '{keyword}': {e}")

    return results

# === MUMSNET SCRAPER ===
def scrape_mumsnet():
    logging.info("🔍 Scraping Mumsnet...")
    results = []

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=chrome_options)

    for keyword in KEYWORDS:
        search_url = f"https://www.mumsnet.com/search?q={quote_plus(keyword)}"
        logging.info(f"➡ Searching Mumsnet for: {keyword}")
        try:
            driver.set_page_load_timeout(30)
            driver.get(search_url)
            time.sleep(4)

            posts = driver.find_elements(By.CSS_SELECTOR, ".search-results__post-title a")
            count = 0
            for post in posts:
                if count >= 10:
                    break
                link = post.get_attribute("href")
                results.append({
                    "Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Forum": "Mumsnet",
                    "Keyword": keyword,
                    "URL": link
                })
                count += 1

            logging.info(f"✅ Found {count} results for '{keyword}' on Mumsnet")

        except Exception as e:
            logging.error(f"❌ Error scraping Mumsnet for '{keyword}': {e}")

    driver.quit()
    return results

# === MAIN SCRIPT ===
def run_scraper():
    sheet = setup_google_sheets()
    all_results = []

    reddit_results = scrape_reddit()
    mumsnet_results = scrape_mumsnet()

    all_results.extend(reddit_results)
    all_results.extend(mumsnet_results)

    if not all_results:
        logging.warning("⚠ No results found.")
        return

    df = pd.DataFrame(all_results)
    rows = df.values.tolist()
    sheet.append_rows(rows)
    logging.info(f"✅ Added {len(rows)} rows to Google Sheet.")

if __name__ == "__main__":
    run_scraper()
