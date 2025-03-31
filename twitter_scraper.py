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

USERNAME = "enter your user name here"
PASSWORD = "enter your password here"
COOKIES_FILE = "twitter_cookies.pkl"
LOG_FILE = "Log.json"

hashtags_file_path = "hashtags_by_category_full.xlsx"
posts_table_path = "PostsTable.xlsx"

hashtags_df = pd.read_excel(hashtags_file_path)
hashtags = hashtags_df["Hashtag"].tolist()

if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as file:
        log_data = json.load(file)
else:
    log_data = {"last_index": 0}
    with open(LOG_FILE, "w") as file:
        json.dump(log_data, file)

options = webdriver.ChromeOptions()
options.add_argument("user-data-dir=/Users/ranmatan21/Library/Application Support/Google/Chrome")
options.add_argument("profile-directory=Profile 3")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920x1080")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--lang=en")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    })
    """
})

def login_to_twitter():
    driver.get("https://twitter.com/")
    time.sleep(5)

    if os.path.exists(COOKIES_FILE):
        print("🍪 loading cookies...")
        with open(COOKIES_FILE, "rb") as file:
            cookies = pickle.load(file)
        for cookie in cookies:
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
    try:
        likes_text = likes_text.lower().replace(",", "").strip()
        if likes_text.endswith('K'):
            return int(float(likes_text[:-1]) * 1000)
        elif likes_text.endswith('M'):
            return int(float(likes_text[:-1]) * 1000000)
        elif likes_text.isdigit():
            return int(likes_text)
        else:
            return 0
    except:
        return 0

def scrape_tweets(hashtag):
    print(f"🔎 searching tweets for: {hashtag}")
    encoded_hashtag = quote(f"{hashtag}")
    driver.get(f"https://twitter.com/search?q={encoded_hashtag}&src=typed_query&f=live")
    time.sleep(random.uniform(5, 8))

    # בדיקת שגיאה מסוג Retry
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Retry')]"))
        )
        print("⚠️ Twitter error page detected. Skipping hashtag.")
        return []  # מדלג להאשטג הבא
    except:
        pass

    SCROLL_PAUSE_TIME = random.uniform(2, 4)
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    max_scrolls = 50
    retry = 0
    max_retry = 3

    collected_tweets = []
    tweet_ids_seen = set()

    while scrolls < max_scrolls:
        try:
            tweets = driver.find_elements(By.XPATH, "//article[@role='article']")

            for tweet in tweets:
                try:
                    post_link = tweet.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                    tweet_url = post_link.get_attribute("href")
                    post_id = [s for s in tweet_url.split("/") if s.isdigit()][-1]

                    if post_id in tweet_ids_seen:
                        continue
                    tweet_ids_seen.add(post_id)

                    user_element = tweet.find_element(By.XPATH, ".//div[@data-testid='User-Name']//span")
                    user_display_name = user_element.text.strip()

                    at_element = tweet.find_elements(By.XPATH, ".//div[@data-testid='User-Name']//span[contains(text(), '@')]")
                    user_id = at_element[0].text.strip() if at_element else ""

                    content_element = tweet.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
                    content = content_element.text.strip()

                    try:
                        detected_lang = langdetect.detect(content)
                        if detected_lang != "en":
                            continue
                    except:
                        continue

                    likes = "0"
                    try:
                        like_elements = tweet.find_elements(By.XPATH, ".//*[@aria-label]")
                        for el in like_elements:
                            aria_label = el.get_attribute("aria-label")
                            if "Like" in aria_label:
                                likes_text = aria_label.split(" ")[0]
                                if likes_text.replace('.', '', 1).replace(',', '').isdigit() or likes_text[-1] in ['K', 'M']:
                                    likes = likes_text.strip()
                                    break
                    except Exception:
                        pass

                    numeric_likes = int(convert_likes_to_number(likes))

                    row = (hashtag, user_display_name, user_id, str(post_id), content, numeric_likes)
                    collected_tweets.append(row)
                    print(f"📥 tweet found: {row}")
                except Exception:
                    continue

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)

            if scrolls % 10 == 0 and scrolls > 0:
                pause = random.uniform(20, 40)
                print(f"😴 resting for {int(pause)} seconds to avoid detection...")
                time.sleep(pause)

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
    try:
        if os.path.exists(file_path):
            df = pd.read_excel(file_path, dtype={"Post_ID": str, "#Likes": int})
        else:
            df = pd.DataFrame(columns=["Hashtag", "User_Name", "User_ID", "Post_ID", "Content", "#Likes"])

        row_df = pd.DataFrame([row], columns=["Hashtag", "User_Name", "User_ID", "Post_ID", "Content", "#Likes"])

        if not df[df["Post_ID"] == row[3]].empty:
            return

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

        wait_time = random.uniform(600, 1200)
        print(f"⏳waiting {int(wait_time)} before the next hashtag")
        time.sleep(wait_time)

    log_data["last_index"] = 0
    with open(LOG_FILE, "w") as file:
        json.dump(log_data, file)

    print("🔁 we gonna start over in few hours ")
    time.sleep(random.uniform(21600, 43200))
