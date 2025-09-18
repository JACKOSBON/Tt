# bot.py
import sqlite3
import time
from datetime import datetime
import telebot
from telebot import types

# ---------------- CONFIG ----------------
TOKEN = "8291608976:AAEeii9LVk-fIGN9nkR7_7gBNPB-fhEDmjM"
ADMIN_ID = 7715257236  # your admin numeric id
DB_PATH = "users.db"
# ----------------------------------------

bot = telebot.TeleBot(TOKEN, parse_mode=None)


# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # users: actual registered users (chat_id known after login)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        user_id TEXT,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        joined_at TEXT,
        banned INTEGER DEFAULT 0
    )
    """)
    # credentials: mapping from user_id -> password (admin adds)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS credentials (
        user_id TEXT PRIMARY KEY,
        password TEXT
    )
    """)
    conn.commit()
    conn.close()


def add_credentials(user_id, password):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO credentials (user_id, password) VALUES (?,?)", (user_id, password))
    conn.commit()
    conn.close()


def remove_credentials(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM credentials WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def check_credentials(user_id, password):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT password FROM credentials WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    return row[0] == password


def get_all_credentials():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM credentials")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def add_user_chat(chat_id, user_id, username=None, first_name=None, last_name=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("""
        INSERT OR REPLACE INTO users (chat_id, user_id, username, first_name, last_name, joined_at, banned)
        VALUES (?,?,?,?,?,COALESCE((SELECT joined_at FROM users WHERE chat_id=?),?), COALESCE((SELECT banned FROM users WHERE chat_id=?), 0))
    """, (chat_id, user_id, username, first_name, last_name, chat_id, now, chat_id))
    conn.commit()
    conn.close()


def user_by_userid(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT chat_id, username, first_name, last_name, joined_at, banned FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def user_by_chatid(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, banned FROM users WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return row


def ban_user_by_userid(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def unban_user_by_userid(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_all_user_chat_ids():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users WHERE banned=0")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def count_users():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    n = cur.fetchone()[0]
    conn.close()
    return n


def list_users(limit=200):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, chat_id, username, first_name, joined_at, banned FROM users ORDER BY joined_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ------------- Keyboards --------------
def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👥 Users Count", "📋 List Users")
    kb.add("➕ Add User", "🗑 Remove Credential")
    kb.add("📝 Broadcast Text", "📤 Broadcast Media")
    kb.add("🚫 Ban User", "♻️ Unban User")
    kb.add("🔐 View Credentials")
    return kb


def user_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📨 My Info", "🔓 Logout")
    return kb


# ------------- Handlers --------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    useridrow = user_by_chatid(chat_id)
    if message.from_user.id == ADMIN_ID:
        bot.send_message(chat_id, "Welcome Admin — control panel ready.", reply_markup=admin_keyboard())
        return

    if useridrow and useridrow[1] == 0:
        # user exists and not banned
        bot.send_message(chat_id, "✅ You are logged in and will receive broadcasts.", reply_markup=user_keyboard())
    else:
        # not logged in or banned
        if useridrow and useridrow[1] == 1:
            bot.send_message(chat_id, "❌ You are banned. Contact admin if this is a mistake.")
        else:
            # prompt to login
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add("🔐 Login")
            bot.send_message(chat_id, "Hello — you are not registered. Please login using the ID and password given by admin.", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "🔐 Login")
def start_login(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "Enter your User ID:")
    bot.register_next_step_handler(msg, login_ask_password)


def login_ask_password(message):
    chat_id = message.chat.id
    user_id = message.text.strip()
    # store user_id temporarily in user-specific state: use message.from_user.id as key in memory
    # simple approach: attach to bot object dict
    bot.temp_login = getattr(bot, "temp_login", {})
    bot.temp_login[chat_id] = {"user_id": user_id}
    msg = bot.send_message(chat_id, "Enter your password:")
    bot.register_next_step_handler(msg, login_check_credentials)


def login_check_credentials(message):
    chat_id = message.chat.id
    pwd = message.text.strip()
    bot.temp_login = getattr(bot, "temp_login", {})
    state = bot.temp_login.get(chat_id)
    if not state:
        bot.send_message(chat_id, "Session expired. Please try login again.")
        return
    user_id = state.get("user_id")
    # remove temp
    try:
        del bot.temp_login[chat_id]
    except:
        pass

    if check_credentials(user_id, pwd):
        # save chat mapping
        add_user_chat(chat_id, user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
        bot.send_message(chat_id, "✅ Login successful. You will receive broadcasts.", reply_markup=user_keyboard())
        try:
            bot.send_message(ADMIN_ID, "User logged in: {} (chat_id: {})".format(user_id, chat_id))
        except:
            pass
    else:
        bot.send_message(chat_id, "❌ Invalid credentials. Contact admin.")


@bot.message_handler(func=lambda m: m.text == "🔓 Logout")
def do_logout(message):
    chat_id = message.chat.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()
    bot.send_message(chat_id, "You have been logged out.", reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(func=lambda m: m.text == "📨 My Info")
def my_info(message):
    chat_id = message.chat.id
    row = user_by_chatid(chat_id)
    if not row:
        bot.send_message(chat_id, "You are not registered.")
        return
    user_id, banned = row
    bot.send_message(chat_id, "Your user ID: {}\nBanned: {}".format(user_id, "Yes" if banned else "No"))


# ------------- Admin-only button handling ---------------
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text is not None)
def admin_buttons(message):
    text = message.text.strip()
    chat_id = message.chat.id

    if text == "👥 Users Count":
        bot.send_message(chat_id, "Total users in DB: {}".format(count_users()))

    elif text == "📋 List Users":
        rows = list_users(200)
        if not rows:
            bot.send_message(chat_id, "No users yet.")
            return
        lines = []
        for r in rows:
            uid, cid, uname, fname, joined, banned = r
            lines.append("{} — {} — @{} — {} — Banned: {}".format(uid, cid or "NA", (uname or "NA"), (fname or ""), ("Yes" if banned else "No")))
        # send chunked
        for i in range(0, len(lines), 30):
            bot.send_message(chat_id, "\n".join(lines[i:i+30]))

    elif text == "➕ Add User":
        msg = bot.send_message(chat_id, "Send new user credentials in format:\n<user_id> <password>\n(example: john123 pass@123)")
        bot.register_next_step_handler(msg, admin_add_user)

    elif text == "🗑 Remove Credential":
        msg = bot.send_message(chat_id, "Send the user_id to remove from credentials (this will prevent login by that id):")
        bot.register_next_step_handler(msg, admin_remove_credential)

    elif text == "🔐 View Credentials":
        creds = get_all_credentials()
        if not creds:
            bot.send_message(chat_id, "No credentials stored.")
        else:
            bot.send_message(chat_id, "Stored user IDs:\n" + "\n".join(creds))

    elif text == "📝 Broadcast Text":
        msg = bot.send_message(chat_id, "Send the text you want to broadcast to all registered (and unbanned) users:")
        bot.register_next_step_handler(msg, admin_broadcast_text)

    elif text == "📤 Broadcast Media":
        bot.send_message(chat_id, "Send or reply to the media/message you want broadcast to all registered users, then reply to it with /broadcast_media (use reply).")

    elif text == "🚫 Ban User":
        msg = bot.send_message(chat_id, "Send user_id to BAN (they will stop receiving broadcasts):")
        bot.register_next_step_handler(msg, admin_ban_user)

    elif text == "♻️ Unban User":
        msg = bot.send_message(chat_id, "Send user_id to UNBAN:")
        bot.register_next_step_handler(msg, admin_unban_user)


# ---------- Admin step functions ----------
def admin_add_user(message):
    txt = message.text.strip()
    parts = txt.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Invalid format. Use: <user_id> <password>")
        return
    user_id = parts[0]
    password = " ".join(parts[1:])
    add_credentials(user_id, password)
    bot.send_message(message.chat.id, "✅ Credential added for user_id: {}".format(user_id))


def admin_remove_credential(message):
    user_id = message.text.strip()
    remove_credentials(user_id)
    bot.send_message(message.chat.id, "✅ Removed credential for: {}".format(user_id))


def admin_broadcast_text(message):
    text = message.text
    targets = get_all_user_chat_ids()
    if not targets:
        bot.send_message(message.chat.id, "No registered users to send.")
        return
    success = 0
    failed = 0
    for uid in targets:
        try:
            bot.send_message(uid, text)
            success += 1
        except Exception as e:
            failed += 1
        time.sleep(0.05)
    bot.send_message(message.chat.id, "Broadcast complete. Success: {}, Failed: {}".format(success, failed))


def admin_ban_user(message):
    user_id = message.text.strip()
    ban_user_by_userid(user_id)
    bot.send_message(message.chat.id, "✅ User {} banned (if present).".format(user_id))


def admin_unban_user(message):
    user_id = message.text.strip()
    unban_user_by_userid(user_id)
    bot.send_message(message.chat.id, "✅ User {} unbanned (if present).".format(user_id))


# ------------- Broadcast media command --------------
# Admin should reply to the media message with /broadcast_media
@bot.message_handler(commands=['broadcast_media'])
def broadcast_media(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        bot.send_message(message.chat.id, "Please reply to the message you want to broadcast with /broadcast_media.")
        return

    target = message.reply_to_message
    targets = get_all_user_chat_ids()
    if not targets:
        bot.send_message(message.chat.id, "No registered users.")
        return

    success = 0
    failed = 0

    # Determine type and get file_id if applicable
    try:
        if target.content_type == "photo":
            # photos is a list, take highest resolution
            file_id = target.photo[-1].file_id
            for uid in targets:
                try:
                    bot.send_photo(uid, file_id, caption=target.caption or "")
                    success += 1
                except:
                    failed += 1
                time.sleep(0.05)

        elif target.content_type == "video":
            file_id = target.video.file_id
            for uid in targets:
                try:
                    bot.send_video(uid, file_id, caption=target.caption or "")
                    success += 1
                except:
                    failed += 1
                time.sleep(0.05)

        elif target.content_type == "document":
            file_id = target.document.file_id
            for uid in targets:
                try:
                    bot.send_document(uid, file_id, caption=target.caption or "")
                    success += 1
                except:
                    failed += 1
                time.sleep(0.05)

        elif target.content_type == "text":
            text = target.text or ""
            for uid in targets:
                try:
                    bot.send_message(uid, text)
                    success += 1
                except:
                    failed += 1
                time.sleep(0.05)

        else:
            # other types: voice, audio, sticker, etc. try generic forward if cannot resend
            for uid in targets:
                try:
                    bot.forward_message(uid, target.chat.id, target.message_id)
                    success += 1
                except:
                    failed += 1
                time.sleep(0.05)

    except Exception as exc:
        bot.send_message(message.chat.id, "Error during broadcast: {}".format(str(exc)))
        return

    bot.send_message(message.chat.id, "Broadcast done. Success: {}, Failed: {}".format(success, failed))


# ------------- Misc: show admin how to get chat_ids -------------
@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'document', 'audio', 'voice'])
def catch_all_register_attempts(message):
    # If normal user sends anything without logging in, tell them to login and show their numeric chat id to admin convenience
    chat_id = message.chat.id
    if message.from_user.id == ADMIN_ID:
        return

    # If user already logged in in DB, just ignore (they're fine)
    row = user_by_chatid(chat_id)
    if row:
        return

    # If user not logged in, send message explaining not registered and show their chat id for admin convenience
    bot.send_message(chat_id, "❌ You are not registered. Contact admin and share your User ID they gave you.\nYour numeric chat id (for admin) is: {}".format(chat_id))


# ------------- Start -------------
if __name__ == "__main__":
    init_db()
    print("Bot started.")
    bot.infinity_polling()
