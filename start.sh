#!/bin/bash

# יצירת ספרייה זמנית לכרום
mkdir -p .chrome
cd .chrome

# הורדת Chromium (גרסה קומפקטית)
wget https://storage.googleapis.com/chromium-browser-snapshots/Linux_x64/1210855/chrome-linux.zip
unzip chrome-linux.zip

# חזרה לתיקיית הפרויקט הראשית
cd ..

# הרצת הסקריפט עם הפנייה ל־Chromium המקומי
python3 twitter_scraper.py
