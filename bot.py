# “””

# TELEGRAM BRIDGE BOT - RENDER DEPLOYMENT
Flask + Webhook mode

“””

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, abort
import telebot

# ─────────────────────────────────────────

# ENV VARIABLES (Render dashboard me set karo)

# ─────────────────────────────────────────

BOT_TOKEN    = os.environ.get(“BOT_TOKEN”, “”)
ADMIN_ID     = int(os.environ.get(“ADMIN_ID”, “0”))
WEBHOOK_HOST = os.environ.get(“RENDER_EXTERNAL_URL”, “”)
CHATS_DIR    = “user_chats”

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

os.makedirs(CHATS_DIR, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(**name**)

WEBHOOK_PATH = f”/webhook/{BOT_TOKEN}”
WEBHOOK_URL  = f”{WEBHOOK_HOST}{WEBHOOK_PATH}”

# ─────────────────────────────────────────

# HELPERS

# ─────────────────────────────────────────

def get_user_map_path():
return os.path.join(CHATS_DIR, “_user_map.json”)

def load_user_map():
path = get_user_map_path()
if os.path.exists(path):
try:
with open(path, “r”, encoding=“utf-8”) as f:
return json.load(f)
except:
return {}
return {}

def save_user_map(data):
with open(get_user_map_path(), “w”, encoding=“utf-8”) as f:
json.dump(data, f, indent=2, ensure_ascii=False)

def register_user(user_id, username, full_name):
user_map = load_user_map()
uid = str(user_id)
safe_name = username.replace(”@”, “”).replace(” “, “*”) if username else f”user*{user_id}”
file_path = os.path.join(CHATS_DIR, f”{safe_name}_{user_id}.txt”)

```
if uid not in user_map:
    user_map[uid] = {"username": username or "", "full_name": full_name, "file": file_path}
    save_user_map(user_map)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("=" * 50 + "\n")
        f.write("  CHAT LOG\n")
        f.write(f"  Name    : {full_name}\n")
        f.write(f"  Username: {username or 'N/A'}\n")
        f.write(f"  User ID : {user_id}\n")
        f.write(f"  Started : {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")

return user_map[uid]["file"]
```

def log_message(file_path, sender, text):
ts = datetime.now().strftime(”%d-%m-%Y %H:%M:%S”)
with open(file_path, “a”, encoding=“utf-8”) as f:
f.write(f”[{ts}] {sender}: {text}\n”)

def find_user_by_username(query):
query = query.replace(”@”, “”).lower()
for uid, info in load_user_map().items():
if info.get(“username”, “”).replace(”@”, “”).lower() == query or uid == query:
return uid, info
return None, None

def get_last_active_user():
latest_time, best_uid, best_info = 0, None, None
for uid, info in load_user_map().items():
fpath = info[“file”]
if os.path.exists(fpath):
mtime = os.path.getmtime(fpath)
if mtime > latest_time:
latest_time, best_uid, best_info = mtime, uid, info
return best_uid, best_info

# ─────────────────────────────────────────

# USER HANDLERS

# ─────────────────────────────────────────

@bot.message_handler(commands=[‘start’])
def handle_start(message):
user = message.from_user
username  = f”@{user.username}” if user.username else None
full_name = f”{user.first_name} {user.last_name or ‘’}”.strip()
file_path = register_user(user.id, username, full_name)
log_message(file_path, “SYSTEM”, “User ne bot start kiya”)

```
try:
    bot.send_message(ADMIN_ID,
        f"*Naya User!*\n"
        f"Name: *{full_name}*\n"
        f"Username: {username or 'N/A'}\n"
        f"ID: `{user.id}`\n"
        f"File: `{os.path.basename(file_path)}`",
        parse_mode="Markdown")
except Exception as e:
    logger.error(e)

bot.send_message(message.chat.id,
    f"Assalam-o-Alaikum, *{user.first_name}!*\n\nApna sawaal ya message type karo.\nHum jald jawab denge!",
    parse_mode="Markdown")
```

@bot.message_handler(
func=lambda m: m.chat.type == “private” and m.from_user.id != ADMIN_ID,
content_types=[‘text’,‘photo’,‘video’,‘voice’,‘document’,‘audio’,‘sticker’,‘location’]
)
def handle_user_message(message):
user = message.from_user
username  = f”@{user.username}” if user.username else None
full_name = f”{user.first_name} {user.last_name or ‘’}”.strip()
file_path = register_user(user.id, username, full_name)

```
content_map = {
    'text':     lambda m: m.text,
    'photo':    lambda m: f"[Photo] {m.caption or ''}",
    'video':    lambda m: f"[Video] {m.caption or ''}",
    'voice':    lambda m: "[Voice Message]",
    'document': lambda m: f"[Document: {m.document.file_name}]",
    'sticker':  lambda m: f"[Sticker {m.sticker.emoji or ''}]",
    'audio':    lambda m: "[Audio]",
    'location': lambda m: f"[Location: {m.location.latitude}, {m.location.longitude}]",
}
msg_text = content_map.get(message.content_type, lambda m: "[Unknown]")(message)
log_message(file_path, "USER", msg_text)

try:
    bot.send_message(ADMIN_ID,
        f"*Message aaya:*\n"
        f"Name: *{full_name}* | {username or 'no username'}\n"
        f"ID: `{user.id}` | File: `{os.path.basename(file_path)}`\n\n"
        f"Reply: `admin- jawab`\n"
        f"Ya: `admin-{username or '@username'} jawab`",
        parse_mode="Markdown")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
except Exception as e:
    logger.error(e)

bot.send_message(message.chat.id, "Message mil gaya! Jald jawab milega.")
```

# ─────────────────────────────────────────

# ADMIN HANDLERS

# ─────────────────────────────────────────

@bot.message_handler(
func=lambda m: (
m.chat.type == “private”
and m.from_user.id == ADMIN_ID
and m.content_type == ‘text’
and m.text is not None
and m.text.lower().startswith(“admin-”)
)
)
def handle_admin_reply(message):
raw = message.text[6:].strip()
if not raw:
bot.send_message(ADMIN_ID, “Khali message! Likho: `admin- tumhara jawab`”, parse_mode=“Markdown”)
return

```
target_uid, target_info, reply_text = None, None, raw
words = raw.split()

if words[0].startswith("@"):
    target_uid, target_info = find_user_by_username(words[0])
    if not target_uid:
        bot.send_message(ADMIN_ID, f"{words[0]} nahi mila. /users se check karo.")
        return
    reply_text = " ".join(words[1:]).strip()
    if not reply_text:
        bot.send_message(ADMIN_ID, "Reply text khali hai!")
        return
else:
    target_uid, target_info = get_last_active_user()
    if not target_uid:
        bot.send_message(ADMIN_ID, "Koi active user nahi mila.")
        return

try:
    bot.send_message(int(target_uid), f"*Admin ka Jawab:*\n\n{reply_text}", parse_mode="Markdown")
    log_message(target_info["file"], "ADMIN", reply_text)
    bot.send_message(ADMIN_ID,
        f"Bhej diya!\nUser: *{target_info['full_name']}* ({target_info.get('username') or 'no username'})",
        parse_mode="Markdown")
except Exception as e:
    bot.send_message(ADMIN_ID, f"Error: {e}")
```

@bot.message_handler(commands=[‘users’], func=lambda m: m.from_user.id == ADMIN_ID)
def cmd_users(message):
user_map = load_user_map()
if not user_map:
bot.send_message(ADMIN_ID, “Koi user nahi abhi.”)
return
text = “*Registered Users:*\n\n”
for uid, info in user_map.items():
fname = info.get(“full_name”, “?”).replace(”*”,””).replace(”_”,””)
text += f”- *{fname}* | {info.get(‘username’) or ‘no username’} | `{uid}`\n”
text += f”\nTotal: {len(user_map)}”
bot.send_message(ADMIN_ID, text, parse_mode=“Markdown”)

@bot.message_handler(commands=[‘file’], func=lambda m: m.from_user.id == ADMIN_ID)
def cmd_file(message):
parts = message.text.split()
if len(parts) < 2:
bot.send_message(ADMIN_ID, “Usage: `/file @username`”, parse_mode=“Markdown”)
return
uid, info = find_user_by_username(parts[1])
if not uid or not os.path.exists(info[“file”]):
bot.send_message(ADMIN_ID, “File nahi mili.”)
return
with open(info[“file”], “rb”) as f:
bot.send_document(ADMIN_ID, f, caption=f”{info[‘full_name’]} ka chat log”,
visible_file_name=os.path.basename(info[“file”]))

@bot.message_handler(commands=[‘help’], func=lambda m: m.from_user.id == ADMIN_ID)
def cmd_help(message):
bot.send_message(ADMIN_ID,
“*Admin Guide:*\n\n”
“`admin- jawab` - last active user ko\n”
“`admin-@username jawab` - specific user ko\n\n”
“/users - saare users\n”
“/file @username - txt file lo\n”
“/help - ye message”,
parse_mode=“Markdown”)

# ─────────────────────────────────────────

# FLASK ROUTES

# ─────────────────────────────────────────

@app.route(WEBHOOK_PATH, methods=[‘POST’])
def webhook():
if request.headers.get(‘content-type’) == ‘application/json’:
update = telebot.types.Update.de_json(request.get_data().decode(‘utf-8’))
bot.process_new_updates([update])
return ‘’, 200
abort(403)

@app.route(’/’, methods=[‘GET’])
def index():
return ‘Telegram Bridge Bot is running!’, 200

@app.route(’/health’, methods=[‘GET’])
def health():
return {‘status’: ‘ok’}, 200

# ─────────────────────────────────────────

# START

# ─────────────────────────────────────────

def setup_webhook():
bot.remove_webhook()
import time; time.sleep(1)
ok = bot.set_webhook(url=WEBHOOK_URL)
logger.info(f”Webhook {‘set’ if ok else ‘FAILED’}: {WEBHOOK_URL}”)

if **name** == “**main**”:
setup_webhook()
PORT = int(os.environ.get(“PORT”, 5000))
app.run(host=“0.0.0.0”, port=PORT)
