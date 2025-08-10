import os
import json
import time
import datetime
import logging
from logging.handlers import RotatingFileHandler
import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote_plus
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === LOGGING CONFIGURATION ===
LOG_FILE = "scraper.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === CONFIGURATION ===
KEYWORDS = [
    "currency transfer", "international money transfer", "send money abroad",
    "send money home", "lump sum transfer", "invest a lump sum",
    "recommend an FX Transfer service", "recommend FX broker",
    "transferring house deposit abroad", "transferring lump sum abroad",
    "sending pension lump sum overseas"
]
HEADERS = {"User-Agent": "Mozilla/5.0"}
RUN_DATE = datetime.datetime.now().strftime('%Y-%m-%d')
RESULTS = []

# === REDDIT SCRAPER ===
def get_unix_time_24hrs_ago():
    return int((datetime.datetime.utcnow() - datetime.timedelta(days=1)).timestamp())

def fetch_reddit_posts(keyword, after_timestamp):
    url = f"https://www.reddit.com/search.json?q={quote_plus(keyword)}&sort=new&limit=100&restrict_sr=0&t=day"
    try:
        logger.info(f"[Reddit] Searching: {keyword}")
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            for post in data["data"]["children"]:
                post_data = post["data"]
                created_utc = post_data["created_utc"]
                if created_utc >= after_timestamp:
                    RESULTS.append({
                        "date": datetime.datetime.fromtimestamp(created_utc).strftime('%Y-%m-%d %H:%M'),
                        "title": post_data["title"],
                        "url": f"https://www.reddit.com{post_data['permalink']}",
                        "forum": "Reddit",
                        "matched_keyword": keyword,
                        "script_run_date": RUN_DATE
                    })
            logger.info(f"[Reddit] Found {len(RESULTS)} total results so far.")
        else:
            logger.warning(f"[Reddit] Non-200 status code for '{keyword}': {response.status_code}")
    except Exception as e:
        logger.error(f"[Reddit] Error for '{keyword}': {e}")

# === MUMSNET SCRAPER ===
def fetch_mumsnet_posts():
    logger.info("[Mumsnet] Starting search...")
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)

    for keyword in KEYWORDS:
        logger.info(f"[Mumsnet] Searching: {keyword}")
        encoded_keyword = quote_plus(keyword)
        page = 1

        while page <= 3:
            url = f"https://www.mumsnet.com/search#/?query={encoded_keyword}&date=day&page={page}"
            driver.get(url)
            time.sleep(3)

            articles = driver.find_elements(By.CSS_SELECTOR, "article.search-result")
            if not articles:
                logger.info(f"[Mumsnet] No more results for '{keyword}' on page {page}")
                break

            for art in articles:
                try:
                    link_el = art.find_element(By.CSS_SELECTOR, "a.text-lg.font-bold")
                    title = link_el.text.strip()
                    post_url = link_el.get_attribute("href").strip()

                    RESULTS.append({
                        "date": "",  # Mumsnet doesn't show exact timestamp
                        "title": title,
                        "url": post_url,
                        "forum": "Mumsnet",
                        "matched_keyword": keyword,
                        "script_run_date": RUN_DATE
                    })
                except Exception as e:
                    logger.debug(f"[Mumsnet] Skipping a result due to: {e}")
            page += 1

    driver.quit()
    logger.info(f"[Mumsnet] Finished. Total results so far: {len(RESULTS)}")

# === GOOGLE SHEETS AUTH ===
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    creds_env = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if creds_env:
        logger.info("Using Google Sheets credentials from environment variable.")
        creds_dict = json.loads(creds_env)
    else:
        logger.info("Using local credentials.json file.")
        with open("credentials.json", "r") as f:
            creds_dict = json.load(f)

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# === SAVE TO GOOGLE SHEET ===
def save_to_google_sheet(results):
    logger.info("📤 Uploading to Google Sheets...")
    client = get_gspread_client()

    spreadsheet_url = "https://docs.google.com/spreadsheets/d/16OtDpKLeXUPzFM_OQerVOQrVaD6XJQ7o8DrSU0bTuGk/edit#gid=0"
    spreadsheet = client.open_by_url(spreadsheet_url)

    try:
        sheet = spreadsheet.worksheet("forum scraper")
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="forum scraper", rows="100", cols="20")

    sheet.clear()

    headers = ["date", "title", "url", "forum", "matched_keyword", "script_run_date"]
    data = [headers]
    for row in results:
        data.append([row.get(col, "") for col in headers])

    sheet.update(f"A1:F{len(data)}", data)
    logger.info(f"✅ Uploaded {len(results)} rows to 'forum scraper' tab.")

# === MAIN RUNNER ===
def run_scraper():
    logger.info("🚀 Starting scraper...")
    since = get_unix_time_24hrs_ago()

    for keyword in KEYWORDS:
        fetch_reddit_posts(keyword, since)
        time.sleep(1)

    fetch_mumsnet_posts()

    if RESULTS:
        save_to_google_sheet(RESULTS)
    else:
        logger.warning("⚠️ No results found.")

if __name__ == "__main__":
    run_scraper()
