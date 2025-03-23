#!/bin/bash

# עדכון והתקנת כרום
apt-get update
apt-get install -y wget unzip curl
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y ./google-chrome-stable_current_amd64.deb

# הרצת הסקריפט שלך
python3 twitter_scraper.py
