# -------------------------------------------------------------
# X (Twitter) hashtag scraper using Selenium + existing cookies
# - Navigates to the "Latest" tab and scrolls to collect tweets
# - Captures: hashtag, user display name, @handle, post_id, text, likes
# - Saves tweets to PostsTable.xlsx and updates UsersTable.xlsx (Tweet_Count)
# Notes:
# * Use responsibly and respect X/Twitter Terms of Service.
# * This script expects a valid cookies file to keep you logged in.
# -------------------------------------------------------------

import time
import random
import pickle
import os
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
from urllib.parse import quote
import openpyxl
import langdetect
import warnings

warnings.simplefilter("ignore")

# --- Personal details / secrets (replace placeholders) ---
# OPTIONAL: Only needed if you later switch to username/password login.
# Recommended: store secrets in environment variables instead of hardcoding.
USERNAME = "<YOUR_TWITTER_USERNAME>"     # e.g., "john_doe"
PASSWORD = "<YOUR_TWITTER_PASSWORD>"     # e.g., use os.environ['TW_PASSWORD']

# Path to your exported/login cookies for X (created separately)
COOKIES_FILE = "twitter_cookies.pkl"

# Log file to remember last processed hashtag index across runs
LOG_FILE = "Log.json"

# --- Local file paths (replace with your actual files/paths) ---
hashtags_file_path = "<PATH_TO_HASHTAGS_XLSX>"  # e.g., "hashtags_by_category_full.xlsx"
posts_table_path = "<PATH_TO_OUTPUT_POSTS_XLSX>"  # e.g., "PostsTable.xlsx"
users_table_path = "<PATH_TO_OUTPUT_USERS_XLSX>"  # e.g., "UsersTable.xlsx"

# Load hashtags list from Excel
hashtags_df = pd.read_excel(hashtags_file_path)
hashtags = hashtags_df["Hashtag"].tolist()

# Initialize or load progress log
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as file:
        log_data = json.load(file)
else:
    log_data = {"last_index": 0}
    with open(LOG_FILE, "w") as file:
        json.dump(log_data, file)

# --- Selenium / Chrome profile settings ---
options = webdriver.ChromeOptions()

# IMPORTANT: Replace with your Chrome user data dir (profile storage folder).
# Examples:
#   Windows: "user-data-dir=C:/Users/<YOU>/AppData/Local/Google/Chrome/User Data"
#   macOS:   "user-data-dir=/Users/<YOU>/Library/Application Support/Google/Chrome"
#   Linux:   "user-data-dir=/home/<YOU>/.config/google-chrome"
options.add_argument("user-data-dir=<PATH_TO_YOUR_CHROME_USER_DATA_DIR>")

# Replace with your Chrome profile name (e.g., "Default", "Profile 1", "Profile 3")
options.add_argument("profile-directory=<YOUR_CHROME_PROFILE_NAME>")

# Common hardening/stability flags
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920x1080")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--lang=en")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

# Start Chrome
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Hide webdriver flag to reduce bot-detection heuristics
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    })
    """
})

def login_to_twitter():
    """
    Log in to X using previously saved cookies.
    If cookies file is missing, exit and ask the user to create it manually.
    """
    driver.get("https://twitter.com/")
    time.sleep(5)

    if os.path.exists(COOKIES_FILE):
        print("🍪 loading cookies...")
        with open(COOKIES_FILE, "rb") as file:
            cookies = pickle.load(file)
        for cookie in cookies:
            # Remove sameSite to avoid Chrome strict errors
            if "sameSite" in cookie:
                del cookie["sameSite"]
            try:
                driver.add_cookie(cookie)
            except:
                pass
        driver.get("https://twitter.com/home")
        time.sleep(5)
    else:
        print("⚠️ cookies file not found. Please create one by logging in manually.")
        driver.quit()
        exit()

def convert_likes_to_number(likes_text):
    """
    Normalize likes text (e.g., '1,234', '2.5K', '1.2M') into an integer.
    Returns 0 if parsing fails.
    """
    try:
        likes_text = likes_text.lower().replace(",", "").strip()
        if likes_text.endswith('k'):  # fixed to match lower() above
            return int(float(likes_text[:-1]) * 1000)
        elif likes_text.endswith('m'):
            return int(float(likes_text[:-1]) * 1_000_000)
        elif likes_text.isdigit():
            return int(likes_text)
        else:
            return 0
    except:
        return 0

def scrape_tweets(hashtag):
    """
    Open the 'Latest' search for the given hashtag and iteratively scroll
    to collect tweets. Skips non-English tweets based on language detection.
    Returns a list of tuples ready to append to Excel.
    """
    print(f"🔎 searching tweets for: {hashtag}")
    encoded_hashtag = quote(f"{hashtag}")
    driver.get(f"https://twitter.com/search?q={encoded_hashtag}&src=typed_query&f=live")
    time.sleep(random.uniform(5, 8))

    # Detect "Retry" error page fast and skip this hashtag if seen
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Retry')]"))
        )
        print("⚠️ Twitter error page detected. Skipping hashtag.")
        return []
    except:
        pass

    # Scroll parameters and simple stuck-page retry
    SCROLL_PAUSE_TIME = random.uniform(3, 6)
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    max_scrolls = 100
    retry = 0
    max_retry = 5

    collected_tweets = []
    tweet_ids_seen = set()

    while scrolls < max_scrolls:
        try:
            tweets = driver.find_elements(By.XPATH, "//article[@role='article']")

            for tweet in tweets:
                try:
                    # Extract tweet URL and numeric post_id
                    post_link = tweet.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                    tweet_url = post_link.get_attribute("href")
                    post_id = [s for s in tweet_url.split("/") if s.isdigit()][-1]

                    # Skip duplicates within this run
                    if post_id in tweet_ids_seen:
                        continue
                    tweet_ids_seen.add(post_id)

                    # User display name and @handle
                    user_element = tweet.find_element(By.XPATH, ".//div[@data-testid='User-Name']//span")
                    user_display_name = user_element.text.strip()
                    at_element = tweet.find_elements(By.XPATH, ".//div[@data-testid='User-Name']//span[contains(text(), '@')]")
                    user_id = at_element[0].text.strip() if at_element else ""

                    # Update users table (counts occurrences per user)
                    append_user_to_excel(user_id, user_display_name, users_table_path)

                    # Tweet text
                    content_element = tweet.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
                    content = content_element.text.strip()

                    # Keep English tweets only (best-effort)
                    try:
                        detected_lang = langdetect.detect(content)
                        if detected_lang != "en":
                            continue
                    except:
                        continue

                    # Parse likes using aria-label (robust to UI changes)
                    likes = "0"
                    try:
                        like_elements = tweet.find_elements(By.XPATH, ".//*[@aria-label]")
                        for el in like_elements:
                            aria_label = el.get_attribute("aria-label")
                            if "Like" in aria_label:
                                likes_text = aria_label.split(" ")[0]
                                if likes_text.replace('.', '', 1).replace(',', '').isdigit() or (len(likes_text) > 1 and likes_text[-1] in ['K', 'M', 'k', 'm']):
                                    likes = likes_text.strip()
                                    break
                    except Exception:
                        pass

                    numeric_likes = int(convert_likes_to_number(likes))

                    # Prepare row for saving
                    row = (hashtag, user_display_name, user_id, str(post_id), content, numeric_likes)
                    collected_tweets.append(row)
                    print(f"📥 tweet found: {row}")
                except Exception:
                    # Ignore per-tweet parsing errors and continue
                    continue

            # Scroll down and wait
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)

            # If page height didn't change, increase retry counter
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                retry += 1
                if retry >= max_retry:
                    print("📉 no more tweets loaded or page stuck, moving to next hashtag.")
                    break
            else:
                retry = 0
                last_height = new_height
                scrolls += 1
        except Exception as e:
            print(f"⚠️ error during scrolling: {e}")
            break

    return collected_tweets

def append_to_excel(row, file_path):
    """
    Append a single tweet row to the posts Excel file.
    Prevents duplicates by Post_ID.
    """
    try:
        if os.path.exists(file_path):
            df = pd.read_excel(file_path, dtype={"Post_ID": str, "#Likes": int}, engine='openpyxl')
        else:
            df = pd.DataFrame(columns=["Hashtag", "User_Name", "User_ID", "Post_ID", "Content", "#Likes"])

        row_df = pd.DataFrame([row], columns=["Hashtag", "User_Name", "User_ID", "Post_ID", "Content", "#Likes"])

        # Skip if Post_ID already exists
        if not df[df["Post_ID"] == row[3]].empty:
            return

        df = pd.concat([df, row_df], ignore_index=True)
        df.to_excel(file_path, index=False, engine='openpyxl')

        print(f"💾 tweet saved to the file: {row}")

    except Exception as e:
        print(f"⚠️ the tweet can't be saved: {e}")

def append_user_to_excel(user_id, user_name, file_path):
    """
    Upsert a user into the users Excel file.
    - If user exists: increment Tweet_Count
    - Else: create a new row with placeholders for Followers/Following
    """
    try:
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
        else:
            df = pd.DataFrame(columns=["User_ID", "User_Name", "Followers", "Following", "Tweet_Count"])

        # Ensure consistent types for ID
        df["User_ID"] = df["User_ID"].astype(str)
        user_id = str(user_id)

        if user_id in df["User_ID"].values:
            df.loc[df["User_ID"] == user_id, "Tweet_Count"] += 1
        else:
            new_row = {
                "User_ID": user_id,
                "User_Name": user_name,
                "Followers": None,
                "Following": None,
                "Tweet_Count": 1
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        df.to_excel(file_path, index=False)
    except Exception as e:
        print(f"⚠️ failed to save user {user_id}: {e}")

# --- Main flow ---

login_to_twitter()

while True:
    for i in range(log_data["last_index"], len(hashtags)):
        hashtag = hashtags[i]
        print(f"\nhashtag: {hashtag}")

        tweets = scrape_tweets(hashtag)

        for row in tweets:
            append_to_excel(row, posts_table_path)

        # Persist progress after each hashtag
        log_data["last_index"] = i + 1
        with open(LOG_FILE, "w") as file:
            json.dump(log_data, file)

        # Random wait to reduce rate-limit/block risk (10–20 min)
        wait_time = random.uniform(600, 1200)
        print(f"⏳waiting {int(wait_time)} seconds before the next hashtag")
        time.sleep(wait_time)

    # Restart from first hashtag on next full pass
    log_data["last_index"] = 0
    with open(LOG_FILE, "w") as file:
        json.dump(log_data, file)

    print("🔁 we gonna start over in few hours ")
    # Sleep 1–2 hours between full cycles
    time.sleep(random.uniform(3600, 7200))
