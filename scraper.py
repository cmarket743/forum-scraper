import os
import time
import datetime
import praw
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === CONFIGURATION ===
KEYWORDS = [
    "currency transfer", "international money transfer", "send money abroad",
    "send money home", "lump sum transfer", "invest a lump sum",
    "recommend an FX Transfer service", "recommend FX broker",
    "transferring house deposit abroad", "transferring lump sum abroad",
    "sending pension lump sum overseas"
]

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
if not creds_json:
    raise Exception("❌ GOOGLE_SHEETS_CREDENTIALS not set")

with open("google-credentials.json", "w") as f:
    f.write(creds_json)

creds = ServiceAccountCredentials.from_json_keyfile_name("google-credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/16OtDpKLeXUPzFM_OQerVOQrVaD6XJQ7o8DrSU0bTuGk/edit").sheet1


# Reddit API setup
reddit = praw.Reddit(
    client_id=os.environ.get("REDDIT_CLIENT_ID"),
    client_secret=os.environ.get("REDDIT_SECRET"),
    user_agent=os.environ.get("REDDIT_USER_AGENT"),
)

RESULTS = []

# === SCRAPERS ===

def scrape_reddit(keyword):
    print(f"🔍 Scraping Reddit for '{keyword}'...")
    try:
        for submission in reddit.subreddit("all").search(keyword, limit=10):
            RESULTS.append({
                "date": datetime.datetime.utcnow().isoformat(),
                "forum": "Reddit",
                "keyword": keyword,
                "title": submission.title,
                "url": f"https://reddit.com{submission.permalink}"
            })
    except Exception as e:
        print(f"❌ Error scraping Reddit for '{keyword}': {e}")


def scrape_mumsnet(keyword):
    print(f"🔍 Scraping Mumsnet for '{keyword}'...")
    try:
        search_url = f"https://www.mumsnet.com/search?q={quote_plus(keyword)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(search_url, headers=headers, timeout=20)

        if resp.status_code != 200:
            print(f"❌ Mumsnet request failed ({resp.status_code}) for '{keyword}'")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.select(".search-results__post-title a")

        for post in posts[:10]:  # only first 10 URLs
            RESULTS.append({
                "date": datetime.datetime.utcnow().isoformat(),
                "forum": "Mumsnet",
                "keyword": keyword,
                "title": post.get_text(strip=True),
                "url": "https://www.mumsnet.com" + post.get("href")
            })

    except Exception as e:
        print(f"❌ Error scraping Mumsnet for '{keyword}': {e}")


# === SAVE RESULTS ===
def save_to_google_sheet(data):
    if not data:
        print("⚠️ No data to save")
        return
    df = pd.DataFrame(data)
    sheet.append_rows(df.values.tolist(), value_input_option="RAW")
    print(f"✅ Saved {len(data)} rows to Google Sheets")


# === MAIN ===
def run_scraper():
    for keyword in KEYWORDS:
        scrape_reddit(keyword)
        scrape_mumsnet(keyword)
        time.sleep(2)

    save_to_google_sheet(RESULTS)


if __name__ == "__main__":
    run_scraper()
