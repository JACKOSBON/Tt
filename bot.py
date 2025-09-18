# corrected_bot.py
import sqlite3
import time
from datetime import datetime
import telebot
from telebot import types

# ---------- CONFIG ----------
TOKEN = ""8291608976:AAEeii9LVk-fIGN9nkR7_7gBNPB-fhEDmjM"
ADMIN_ID = 7715257236  # Replace with your Telegram user id
DB_PATH = "users.db"
# ----------------------------

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        added_at TEXT
    )
    """)
    conn.commit()
    conn.close()


def add_user(chat_id, username=None, first_name=None, last_name=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    try:
        cur.execute("INSERT INTO users (chat_id, username, first_name, last_name, added_at) VALUES (?,?,?,?,?)",
                    (chat_id, username, first_name, last_name, now))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


def user_exists(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE chat_id=?", (chat_id,))
    result = cur.fetchone()
    conn.close()
    return bool(result)


def get_all_user_chat_ids():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
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


def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("👥 Users Count", "📋 List Users")
    markup.add("➕ Add User")
    markup.add("📝 Broadcast Text", "📤 Broadcast Message")
    return markup


@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        bot.send_message(chat_id, "Welcome Admin! Choose an option:", reply_markup=admin_keyboard())
    else:
        if user_exists(user_id):
            bot.send_message(chat_id, "✅ You are registered. Wait for admin broadcasts.")
        else:
            bot.send_message(chat_id, "❌ You are not registered. Contact Admin.")


@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id != ADMIN_ID:
        return

    if text == "👥 Users Count":
        bot.send_message(chat_id, "Total registered users: {}".format(count_users()))

    elif text == "📋 List Users":
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT chat_id, username FROM users LIMIT 50")
        rows = cur.fetchall()
        conn.close()
        if not rows:
            bot.send_message(chat_id, "No users yet.")
        else:
            user_list = "\n".join(["{} - @{}".format(cid, (uname or 'NA')) for cid, uname in rows])
            bot.send_message(chat_id, "<b>Users List:</b>\n{}".format(user_list))

    elif text == "➕ Add User":
        msg = bot.send_message(chat_id, "✍️ Send the User's Chat ID to add:")
        bot.register_next_step_handler(msg, do_add_user)

    elif text == "📝 Broadcast Text":
        msg = bot.send_message(chat_id, "✍️ Enter the text you want to broadcast:")
        bot.register_next_step_handler(msg, do_broadcast_text)

    elif text == "📤 Broadcast Message":
        bot.send_message(chat_id, "Reply to the message you want to broadcast and type /broadcast")


def do_add_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        chat_id = int(message.text.strip())
    except:
        bot.send_message(ADMIN_ID, "❌ Invalid Chat ID")
        return

    success = add_user(chat_id)
    if success:
        bot.send_message(ADMIN_ID, "✅ User {} added successfully.".format(chat_id))
        try:
            bot.send_message(chat_id, "✅ Admin has registered you. You will now receive broadcasts.")
        except:
            pass
    else:
        bot.send_message(ADMIN_ID, "⚠️ User {} already exists or error occurred.".format(chat_id))


def do_broadcast_text(message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text
    users = get_all_user_chat_ids()
    success, fail = 0, 0
    for uid in users:
        try:
            bot.send_message(uid, text)
            success += 1
        except:
            fail += 1
        time.sleep(0.05)
    bot.send_message(ADMIN_ID, "📢 Broadcast Done!\n✅ Success: {}\n❌ Failed: {}".format(success, fail))


@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        bot.send_message(message.chat.id, "❌ Please reply to the message you want to broadcast.")
        return

    target_msg = message.reply_to_message
    users = get_all_user_chat_ids()
    success, fail = 0, 0
    for uid in users:
        try:
            bot.forward_message(uid, target_msg.chat.id, target_msg.message_id)
            success += 1
        except:
            fail += 1
        time.sleep(0.05)
    bot.send_message(ADMIN_ID, "📢 Broadcast Done!\n✅ Success: {}\n❌ Failed: {}".format(success, fail))


if __name__ == "__main__":
    init_db()
    print("Bot is running...")
    bot.infinity_polling()
