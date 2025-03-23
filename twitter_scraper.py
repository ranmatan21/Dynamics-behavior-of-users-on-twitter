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

# פרטי ההתחברות לטוויטר
USERNAME = "ranmatan21"
PASSWORD = "Ran210918!"
COOKIES_FILE = "twitter_cookies.pkl"
LOG_FILE = "Log.json"

# טוען את רשימת ההאשטגים מקובץ האקסל
hashtags_file_path = "hashtags_by_category_full.xlsx"
posts_table_path = "PostsTable.xlsx"
changes_table_path = "Changes.xlsx"

# קריאת האשטגים מהקובץ (לפי הסדר בטבלה)
hashtags_df = pd.read_excel(hashtags_file_path)
hashtags = hashtags_df["Hashtag"].tolist()

# קריאת קובץ לוג או אתחול חדש
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as file:
        log_data = json.load(file)
else:
    log_data = {"last_index": 0}
    with open(LOG_FILE, "w") as file:
        json.dump(log_data, file)

# אתחול הדפדפן
options = webdriver.ChromeOptions()
#options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920x1080")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--lang=en")
options.binary_location = "/usr/bin/google-chrome"
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)

def login_to_twitter():
    driver.get("https://twitter.com/login")
    time.sleep(random.uniform(5, 10))

    try:
        if os.path.exists(COOKIES_FILE):
            print("loading cookies...")
            with open(COOKIES_FILE, "rb") as file:
                cookies = pickle.load(file)
            for cookie in cookies:
                driver.add_cookie(cookie)
            driver.get("https://twitter.com/home")
            time.sleep(random.uniform(5, 10))
            return

        username_input = driver.find_element(By.NAME, "text")
        username_input.send_keys(USERNAME)
        username_input.send_keys(Keys.RETURN)
        time.sleep(random.uniform(5, 10))

        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(PASSWORD)
        password_input.send_keys(Keys.RETURN)
        time.sleep(random.uniform(5, 10))

        with open(COOKIES_FILE, "wb") as file:
            pickle.dump(driver.get_cookies(), file)
    except Exception as e:
        print("login error:", e)
        driver.quit()
        exit()

def scrape_tweets(hashtag):
    print(f"🔎 searching tweets for: {hashtag}")
    encoded_hashtag = quote(f"#{hashtag}")
    driver.get(f"https://twitter.com/search?q={encoded_hashtag}&src=typed_query&f=live")
    time.sleep(random.uniform(5, 8))

    SCROLL_PAUSE_TIME = random.uniform(2, 4)
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    max_scrolls = 200

    collected_tweets = []
    tweet_ids_seen = set()

    while scrolls < max_scrolls:
        tweets = driver.find_elements(By.XPATH, "//article[@role='article']")

        for tweet in tweets:
            try:
                post_link = tweet.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                tweet_url = post_link.get_attribute("href")
                post_id = tweet_url.split("/")[-1]

                if post_id in tweet_ids_seen:
                    continue
                tweet_ids_seen.add(post_id)

                user_element = tweet.find_element(By.XPATH, ".//div[@dir='ltr']//span")
                user_id = user_element.text.strip()

                content = tweet.text.strip()

                # סינון שפה - רק אנגלית לדוגמה
                try:
                    detected_lang = langdetect.detect(content)
                    if detected_lang != "en":
                        continue
                except:
                    continue

                likes = "0"
                try:
                    like_button = tweet.find_element(By.XPATH, ".//div[@data-testid='like']")
                    spans = like_button.find_elements(By.TAG_NAME, "span")
                    if spans:
                        likes_text = spans[-1].text.strip()
                        if likes_text:
                            likes = likes_text
                except:
                    pass

                row = (hashtag, user_id, post_id, content, likes)
                collected_tweets.append(row)
                print(f"📥 tweet found: {row}")
            except Exception as e:
                continue

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)

        try:
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scrolls += 1

    return collected_tweets

def append_to_excel(row, file_path):
    try:
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
        else:
            df = pd.DataFrame(columns=["Hashtag", "User_ID", "Post_ID", "Content", "#Likes"])

        row_df = pd.DataFrame([row], columns=["Hashtag", "User_ID", "Post_ID", "Content", "#Likes"])

        existing = df[df["Post_ID"] == row[2]]
        if not existing.empty:
            existing_row = existing.iloc[0]
            changes = []
            if existing_row["Content"] != row[3]:
                changes.append({
                    "Post_ID": row[2],
                    "Field": "Content",
                    "Old_Value": existing_row["Content"],
                    "New_Value": row[3],
                    "User_ID": row[1],
                    "Hashtag": row[0],
                    "Change_Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            if str(existing_row["#Likes"]) != str(row[4]):
                changes.append({
                    "Post_ID": row[2],
                    "Field": "#Likes",
                    "Old_Value": existing_row["#Likes"],
                    "New_Value": row[4],
                    "User_ID": row[1],
                    "Hashtag": row[0],
                    "Change_Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            if changes:
                changes_df = pd.DataFrame(changes)
                if os.path.exists(changes_table_path):
                    existing_changes = pd.read_excel(changes_table_path)
                    changes_df = pd.concat([existing_changes, changes_df], ignore_index=True)
                changes_df.to_excel(changes_table_path, index=False)
        else:
            df = pd.concat([df, row_df], ignore_index=True)
            df.to_excel(file_path, index=False)
    except Exception as e:
        print(f"⚠️ the tweet can't be saved: {e}")

login_to_twitter()

while True:
    for i in range(log_data["last_index"], len(hashtags)):
        hashtag = hashtags[i]
        print(f"\nhashtag: {hashtag}")

        tweets = scrape_tweets(hashtag)

        for row in tweets:
            append_to_excel(row, posts_table_path)
            print(f"💾 tweet saved to the file: {row}")

        log_data["last_index"] = i + 1
        with open(LOG_FILE, "w") as file:
            json.dump(log_data, file)

        wait_time = random.uniform(300, 900)
        print(f"⏳waiting {int(wait_time)} before the next hashtag")
        time.sleep(wait_time)

    log_data["last_index"] = 0
    with open(LOG_FILE, "w") as file:
        json.dump(log_data, file)

    print("🔁 we gonna start over in few hours ")
    time.sleep(random.uniform(21600, 43200))
