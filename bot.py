import os
import time
from datetime import date
import schedule
from instagrapi import Client

USERNAME = os.environ.get("IG_USERNAME")
PASSWORD = os.environ.get("IG_PASSWORD")

SESSION_FILE = "session.json"

def get_client():
    cl = Client()
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
    cl.login(USERNAME, PASSWORD)
    cl.dump_settings(SESSION_FILE)
    return cl

def update_bio():
    today = date.today()
    birthday = date(today.year, 7, 14)
    if today > birthday:
        birthday = date(today.year + 1, 7, 14)
    
    days_left = (birthday - today).days
    
    if days_left == 0:
        bio_text = "🎂 Aaj meri jaan ka Birthday hai! 🎉❤️"
    elif days_left == 1:
        bio_text = "💕 Kal meri jaan ka birthday hai! 🎂"
    else:
        bio_text = f"🎂 Meri jaan ke birthday mein {days_left} din baaki! ❤️"
    
    try:
        cl = get_client()
        time.sleep(5)
        cl.account_edit(biography=bio_text)
        print(f"✅ Bio update hua: {bio_text}")
    except Exception as e:
        print(f"❌ Error: {e}")

schedule.every().day.at("00:00").do(update_bio)
update_bio()

while True:
    schedule.run_pending()
    time.sleep(60)
