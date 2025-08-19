# -------------------------------------------------------------
# X (Twitter) user profile updater + (optional) tweets scraper
# - Reads users from UsersTable.xlsx (column: User_ID)
# - For each user: opens profile, extracts fields, logs changes to Changes.xlsx
# - (Optional) scrapes recent tweets into PostsByUsers.xlsx
# Notes:
# * Use responsibly and respect X/Twitter Terms of Service.
# * Script expects a valid cookies file to keep you logged in.
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

# --- Credentials (optional) ---
# If you ONLY use cookies, keep these empty. If you later switch to username/password
# login, fill in your own credentials here (or prefer environment variables).
USERNAME = "<YOUR_TWITTER_USERNAME>"  # e.g., "john_doe"
PASSWORD = "<YOUR_TWITTER_PASSWORD>"  # e.g., use env var instead of hardcoding

# --- Local files (replace with your own paths/file names if different) ---
COOKIES_FILE = "<PATH_TO_COOKIES_PKL>"  # e.g., "twitter_cookies.pkl" saved from a manual login
LOG_FILE = "Log.json"                   # progress log (keeps last_index)

# Output / input Excel files:
users_posts_file_path = "<PATH_TO_PostsByUsers.xlsx>"  # e.g., "PostsByUsers.xlsx"
changes_table_path    = "<PATH_TO_Changes.xlsx>"       # e.g., "Changes.xlsx"
users_table_path      = "<PATH_TO_UsersTable.xlsx>"    # e.g., "UsersTable.xlsx"

# --- Load users from UsersTable.xlsx (expects a 'User_ID' column with @handles) ---
users_df = pd.read_excel(users_table_path)
users = users_df["User_ID"].tolist()

# --- Init or load progress log ---
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as file:
        log_data = json.load(file)
else:
    log_data = {"last_index": 0}
    with open(LOG_FILE, "w") as file:
        json.dump(log_data, file)

# --- Selenium / Chrome options ---
options = webdriver.ChromeOptions()

# If you want to use a specific Chrome profile, replace the placeholders and UNCOMMENT both lines:
# options.add_argument("user-data-dir=<ABSOLUTE_PATH_TO_CHROME_USER_DATA_DIR>")  # macOS example: /Users/<you>/Library/Application Support/Google/Chrome
# options.add_argument("profile-directory=<YOUR_CHROME_PROFILE_NAME>")          # e.g., "Default", "Profile 1", "Profile 3"

# Stability / stealth flags:
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920x1080")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--lang=en")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Reduce bot-detection heuristics by hiding navigator.webdriver
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    })
    """
})

def login_to_twitter():
    """
    Log in to X using previously saved cookies. If cookies file is missing,
    stop and ask the user to create it by logging in manually once.
    """
    driver.get("https://twitter.com/")
    time.sleep(5)

    if os.path.exists(COOKIES_FILE):
        print("🍪 loading cookies...")
        with open(COOKIES_FILE, "rb") as file:
            cookies = pickle.load(file)
        for cookie in cookies:
            # Avoid Chrome complaints about sameSite
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
        if likes_text.endswith('k'):             # works after lower()
            return int(float(likes_text[:-1]) * 1000)
        elif likes_text.endswith('m'):
            return int(float(likes_text[:-1]) * 1_000_000)
        elif likes_text.isdigit():
            return int(likes_text)
        else:
            return 0
    except:
        return 0

def normalize(value):
    """
    Convert numeric-looking values to a clean string (e.g., 3.0 -> '3').
    """
    try:
        val = float(value)
        if val.is_integer():
            return str(int(val))
        return str(val)
    except:
        return str(value)

def update_user_profile_data(user_id: str):
    """
    Open a user's profile by @handle and update UsersTable.xlsx.
    Logs field-level changes to Changes.xlsx (with a basic Delta).
    """
    print(f"🔍 Updating profile data for: {user_id}")
    driver.get(f"https://twitter.com/{user_id}")
    time.sleep(random.uniform(5, 8))

    def safe_get_text(xpath):
        try:
            return driver.find_element(By.XPATH, xpath).text.strip()
        except:
            return ""

    def safe_get_attr(xpath, attr):
        try:
            return driver.find_element(By.XPATH, xpath).get_attribute(attr)
        except:
            return ""

    # Profile fields (best-effort selectors; UI may change over time)
    bio       = safe_get_text("//div[@data-testid='UserDescription']")
    location  = safe_get_text("//span[@data-testid='UserLocation']")
    website   = safe_get_text("//span[@data-testid='UserUrl']")
    dob       = safe_get_text("//span[@data-testid='UserBirthdate']")
    join_date = safe_get_text("//span[@data-testid='UserJoinDate']")

    # Following / Followers counts (may break if X changes DOM)
    try:
        following = driver.find_element(By.XPATH, "//a[contains(@href,'/following')]//span[1]/span").text.replace(",", "")
        following = int(following)
    except:
        following = None

    try:
        followers_element = driver.find_element(By.XPATH, "//a[.//span[text()='Followers']]/span[1]")
        followers = int(followers_element.text.replace(",", ""))
    except:
        followers = None

    # Images
    profile_img_url = safe_get_attr("//img[contains(@src, 'profile_images')]", "src")
    header_img_url  = safe_get_attr("//img[contains(@src, 'profile_banners')]", "src")

    # Upsert into UsersTable.xlsx and log changes
    try:
        users_df = pd.read_excel(users_table_path)
        if user_id in users_df["User_ID"].astype(str).values:
            idx = users_df[users_df["User_ID"].astype(str) == str(user_id)].index[0]

            original_user_name   = users_df.loc[idx, "User_Name"]
            extracted_user_name  = safe_get_text("//div[@data-testid='UserProfileHeader_Items']/preceding-sibling::div//span[1]")
            if extracted_user_name:
                # Handle possible ID or display name changes
                if str(users_df.loc[idx, "User_ID"]) != str(user_id):
                    log_changes(user_id, original_user_name, "User_ID", users_df.loc[idx, "User_ID"], user_id, changes_table_path)
                    users_df.loc[idx, "User_ID"] = user_id

                if str(users_df.loc[idx, "User_Name"]) != extracted_user_name:
                    log_changes(user_id, original_user_name, "User_Name", users_df.loc[idx, "User_Name"], extracted_user_name, changes_table_path)
                    users_df.loc[idx, "User_Name"] = extracted_user_name

            fields_to_check = {
                "Bio": bio,
                "Location": location,
                "Website": website,
                "Date of Birth": dob,
                "Join Date": join_date,
                "Following": following,
                "Followers": followers,
                "Profile Image": profile_img_url,
                "Cover Image": header_img_url
            }

            for field, new_value in fields_to_check.items():
                if field in users_df.columns:
                    old_value = users_df.loc[idx, field]
                    # Skip if unchanged (also ignores cosmetic '.0')
                    if str(old_value).rstrip('.0') == str(new_value).rstrip('.0'):
                        continue
                    # Log change only if old_value was set (not empty/NaN)
                    if not (pd.isna(old_value) or str(old_value).strip() == ''):
                        log_changes(user_id, original_user_name, field, old_value, new_value, changes_table_path)
                    users_df.loc[idx, field] = new_value

            users_df.to_excel(users_table_path, index=False)
            print(f"✅ Profile data updated for {user_id}")
        else:
            print(f"⚠️ User {user_id} not found in table.")
    except Exception as e:
        print(f"❌ Failed to update profile data for {user_id}: {e}")

def log_changes(user_id, user_name, field_name, old_value, new_value, file_path):
    """
    Append a change record to Changes.xlsx, including a basic Delta:
    - Numeric fields: new - old
    - Text fields: length(new) - length(old)
    """
    try:
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
        else:
            df = pd.DataFrame(columns=["User_ID", "User_Name", "Changed_Field", "Prev_Value", "Curr_Value", "Delta"])

        # Compute delta (numeric if possible; otherwise by text length)
        delta = ""
        try:
            delta = float(new_value) - float(old_value)
        except (ValueError, TypeError):
            try:
                delta = len(str(new_value)) - len(str(old_value))
            except:
                delta = ""

        new_row = {
            "User_ID": user_id,
            "User_Name": user_name,
            "Changed_Field": field_name,
            "Prev_Value": old_value,
            "Curr_Value": new_value,
            "Delta": delta
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(file_path, index=False, engine="openpyxl")

        print(f"✅ logged change: {field_name} - {old_value} ➜ {new_value} (Δ = {delta})")

    except Exception as e:
        print(f"⚠️ failed to log change for {user_id}, {field_name}: {e}")

def scrape_users(user_handle: str):
    """
    (Optional) On a user's timeline, collect recent tweets (EN only) with id, content, date, likes.
    """
    print(f"🔎 searching tweets for: {user_handle}")
    driver.get(f"https://twitter.com/{user_handle}")
    time.sleep(random.uniform(5, 8))

    # Fast detect "Retry" error page and skip
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Retry')]"))
        )
        print("⚠️ Twitter error page detected. Skipping user.")
        return []
    except:
        pass

    SCROLL_PAUSE_TIME = random.uniform(3, 6)
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls, max_scrolls = 0, 10
    retry, max_retry = 0, 5

    collected_tweets = []
    tweet_ids_seen = set()

    while scrolls < max_scrolls:
        try:
            tweets = driver.find_elements(By.XPATH, "//article[@role='article']")

            for tweet in tweets:
                try:
                    # Tweet URL → numeric id
                    post_link = tweet.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                    tweet_url = post_link.get_attribute("href")
                    tweet_id = [s for s in tweet_url.split("/") if s.isdigit()][-1]

                    if tweet_id in tweet_ids_seen:
                        continue
                    tweet_ids_seen.add(tweet_id)

                    # Display name and @handle
                    user_element = tweet.find_element(By.XPATH, ".//div[@data-testid='User-Name']//span")
                    user_display_name = user_element.text.strip()
                    at_element = tweet.find_elements(By.XPATH, ".//div[@data-testid='User-Name']//span[contains(text(), '@')]")
                    at_handle = at_element[0].text.strip() if at_element else ""

                    # Tweet content
                    content_element = tweet.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
                    content = content_element.text.strip()

                    # Post date (UTC ISO 8601 → yyyy-mm-dd)
                    time_element = tweet.find_element(By.XPATH, ".//time")
                    post_date = time_element.get_attribute("datetime") if time_element else ""
                    post_date = post_date[:10]

                    # Keep English tweets only (best-effort)
                    try:
                        detected_lang = langdetect.detect(content)
                        if detected_lang != "en":
                            continue
                    except:
                        continue

                    # Likes via aria-label
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

                    # Row for Excel
                    row = (at_handle, user_display_name, str(tweet_id), content, post_date)
                    collected_tweets.append(row)
                    print(f"📥 tweet found: {row}")
                except Exception:
                    continue

            # Scroll and wait
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                retry += 1
                if retry >= max_retry:
                    print("📉 no more tweets loaded or page stuck, moving to next user.")
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
    Append a single tweet row to PostsByUsers.xlsx, skipping duplicates by tweet_id.
    """
    try:
        if os.path.exists(file_path):
            df = pd.read_excel(file_path, dtype={"tweet_id": str}, engine='openpyxl')
        else:
            df = pd.DataFrame(columns=["user_id", "user_name", "tweet_id", "content", "post_date"])

        row_df = pd.DataFrame([row], columns=["user_id", "user_name", "tweet_id", "content", "post_date"])

        # Skip if tweet_id already exists
        if not df[df["tweet_id"] == row[2]].empty:
            return

        df = pd.concat([df, row_df], ignore_index=True)
        df.to_excel(file_path, index=False, engine='openpyxl')

        print(f"💾 tweet saved to the file: {row}")

    except Exception as e:
        print(f"⚠️ the tweet can't be saved: {e}")

# --- Main flow ---
login_to_twitter()

while True:
    for i in range(log_data["last_index"], len(users)):
        user = users[i]  # expected format: '@handle' or handle without '@'
        print(f"\nuser: {user}")

        # Update profile fields + log changes
        update_user_profile_data(user)  # ← for debugging a single user: put a fixed handle here

        # (Optional) collect recent tweets for this user:
        # tweets = scrape_users(user)
        # for row in tweets:
        #     append_to_excel(row, users_posts_file_path)

        # Persist progress after each user
        log_data["last_index"] = i + 1
        with open(LOG_FILE, "w") as file:
            json.dump(log_data, file)

        # Random wait between users (30–60s)
        wait_time = random.uniform(30, 60)
        print(f"⏳waiting {int(wait_time)} seconds before the next user")
        time.sleep(wait_time)

    # Restart from first user on next full pass
    log_data["last_index"] = 0
    with open(LOG_FILE, "w") as file:
        json.dump(log_data, file)

    print("🔁 we gonna start over in few minutes ")
    time.sleep(random.uniform(300, 600))
