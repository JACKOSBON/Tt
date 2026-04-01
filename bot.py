import os
import time
from datetime import date
from instagrapi import Client

USERNAME = os.environ.get("IG_USERNAME")
PASSWORD = os.environ.get("IG_PASSWORD")

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
    
    cl = Client()
    cl.login(USERNAME, PASSWORD)
    time.sleep(5)
    cl.account_edit(biography=bio_text)
    print(f"✅ Bio update hua: {bio_text}")

update_bio()
