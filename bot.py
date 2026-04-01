import instagrapi
from datetime import date
import schedule
import time
import json
import os

USERNAME = "mxluv__"
PASSWORD = "TAUSEEF07"
SESSION_FILE = "session.json"

def get_client():
    cl = instagrapi.Client()
    
    # Purana session load karo agar available ho
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
        cl.login(USERNAME, PASSWORD)
    else:
        cl.login(USERNAME, PASSWORD)
        cl.dump_settings(SESSION_FILE)  # Session save karo
    
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
        time.sleep(3)  # Suspicious activity se bachne ke liye delay
        cl.account_edit(biography=bio_text)
        print(f"✅ Bio update hua: {bio_text}")
    except Exception as e:
        print(f"❌ Error: {e}")

schedule.every().day.at("00:00").do(update_bio)
update_bio()  # Abhi ek baar chalao

while True:
    schedule.run_pending()
    time.sleep(60)
