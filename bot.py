import os
import asyncio
import threading
from flask import Flask
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ["BOT_TOKEN"]
MONGODB_URI = os.environ["MONGODB_URI"]
ADMIN_IDS   = [a.strip() for a in os.environ.get("ADMIN_IDS", "").split(",")]

# ─── MongoDB ──────────────────────────────────────────────────────────────────
client  = MongoClient(MONGODB_URI)
db      = client["supportbot"]
users   = db["users"]
sessions = db["sessions"]
messages = db["messages"]

# ─── Flask (keep-alive for Render) ────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "🤖 Bot is running!", 200

@flask_app.route("/health")
def health():
    return {"status": "ok"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def is_admin(chat_id):
    return str(chat_id) in ADMIN_IDS

def get_or_create_user(tg_user):
    user = users.find_one({"telegramId": str(tg_user.id)})
    if not user:
        users.insert_one({
            "telegramId":  str(tg_user.id),
            "firstName":   tg_user.first_name or "",
            "lastName":    tg_user.last_name or "",
            "username":    tg_user.username or "",
        })
        user = users.find_one({"telegramId": str(tg_user.id)})
    return user

def get_active_session(user_doc):
    return sessions.find_one({"telegramId": user_doc["telegramId"], "status": "open"})

def get_reply_keyboard(user_telegram_id, session_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↩️ Reply",        callback_data=f"reply_{user_telegram_id}_{session_id}"),
        InlineKeyboardButton("✅ Close Session", callback_data=f"close_{session_id}"),
    ]])

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if is_admin(chat_id):
        await update.message.reply_text(
            "👑 *Admin Panel*\n\n"
            "/users — All users\n"
            "/sessions — Open sessions\n"
            "/reply <userId> <msg> — Reply to user\n"
            "/close <sessionId> — Close session\n"
            "/broadcast <msg> — Message all users",
            parse_mode="Markdown"
        )
    else:
        get_or_create_user(update.effective_user)
        await update.message.reply_text(
            "👋 *Welcome!*\n\nAdmin se baat karne ke liye bas message likhein.\n_Hum jald reply karenge!_ 😊",
            parse_mode="Markdown"
        )

# ─── User message → Admin ──────────────────────────────────────────────────────
async def user_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if is_admin(chat_id):
        return

    user = get_or_create_user(update.effective_user)

    # Open session agar nahi hai toh banao
    session = get_active_session(user)
    if not session:
        sessions.insert_one({"telegramId": user["telegramId"], "status": "open"})
        session = get_active_session(user)

    session_id = str(session["_id"])
    text = update.message.text or "[media]"

    # Message save karo
    messages.insert_one({
        "sessionId": session_id,
        "fromUser":  True,
        "text":      text,
    })

    # Sabhi admins ko forward karo
    info = (
        f"👤 *{user['firstName']} {user['lastName']}* "
        f"(@{user['username'] or 'no username'})\n"
        f"🆔 `{user['telegramId']}`\n"
        f"📋 Session: `{session_id}`\n\n"
        f"💬 {text}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(
                chat_id=admin_id,
                text=info,
                parse_mode="Markdown",
                reply_markup=get_reply_keyboard(user["telegramId"], session_id)
            )
        except Exception as e:
            print(f"Admin {admin_id} ko message nahi gaya: {e}")

    await update.message.reply_text(
        "✅ Message deliver ho gaya! Admin jald reply karenge.", parse_mode="Markdown"
    )

# ─── Callback buttons ─────────────────────────────────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    admin_id = str(query.from_user.id)

    if data.startswith("reply_"):
        _, user_id, session_id = data.split("_", 2)
        await query.message.reply_text(
            f"✏️ Reply likhein:\n`/reply {user_id} aapka message yahan`",
            parse_mode="Markdown"
        )

    elif data.startswith("close_"):
        session_id = data.split("_", 1)[1]
        await close_session_by_id(session_id, admin_id, ctx)

# ─── /reply ───────────────────────────────────────────────────────────────────
async def reply_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        return
    if len(ctx.args) < 2:
        await update.message.reply_text("❌ Format: `/reply <userId> <message>`", parse_mode="Markdown")
        return

    target_id = ctx.args[0]
    text = " ".join(ctx.args[1:])

    try:
        await ctx.bot.send_message(target_id, f"💬 *Admin ka jawab:*\n\n{text}", parse_mode="Markdown")
        await update.message.reply_text(f"✅ Reply bheji `{target_id}` ko.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ─── /close ───────────────────────────────────────────────────────────────────
async def close_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        return
    if not ctx.args:
        await update.message.reply_text("❌ Format: `/close <sessionId>`", parse_mode="Markdown")
        return
    await close_session_by_id(ctx.args[0], str(update.effective_chat.id), ctx)

async def close_session_by_id(session_id, admin_chat_id, ctx):
    from bson import ObjectId
    try:
        session = sessions.find_one_and_update(
            {"_id": ObjectId(session_id)},
            {"$set": {"status": "closed"}}
        )
        if not session:
            await ctx.bot.send_message(admin_chat_id, "❌ Session nahi mila.")
            return
        user = users.find_one({"telegramId": session["telegramId"]})
        if user:
            await ctx.bot.send_message(
                session["telegramId"],
                "✅ *Aapki query resolve ho gayi!* Phir kisi bhi waqt message karein. 😊",
                parse_mode="Markdown"
            )
        await ctx.bot.send_message(admin_chat_id, f"✅ Session `{session_id}` close ho gaya.", parse_mode="Markdown")
    except Exception as e:
        await ctx.bot.send_message(admin_chat_id, f"❌ Error: {e}")

# ─── /users ───────────────────────────────────────────────────────────────────
async def users_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        return
    all_users = list(users.find().sort("_id", -1).limit(20))
    if not all_users:
        await update.message.reply_text("Koi user nahi mila.")
        return
    lines = [
        f"{i+1}. *{u['firstName']} {u['lastName']}* (@{u['username'] or '-'})\n   ID: `{u['telegramId']}`"
        for i, u in enumerate(all_users)
    ]
    await update.message.reply_text("👥 *Users (latest 20):*\n\n" + "\n\n".join(lines), parse_mode="Markdown")

# ─── /sessions ────────────────────────────────────────────────────────────────
async def sessions_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        return
    open_sessions = list(sessions.find({"status": "open"}).sort("_id", -1))
    if not open_sessions:
        await update.message.reply_text("✅ Koi open session nahi hai.")
        return
    lines = []
    for s in open_sessions:
        user = users.find_one({"telegramId": s["telegramId"]})
        name = f"{user['firstName']} {user['lastName']}" if user else "Unknown"
        lines.append(f"🟡 *{name}* (`{s['telegramId']}`)\n   Session: `{s['_id']}`")
    await update.message.reply_text("📋 *Open Sessions:*\n\n" + "\n\n".join(lines), parse_mode="Markdown")

# ─── /broadcast ───────────────────────────────────────────────────────────────
async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        return
    if not ctx.args:
        await update.message.reply_text("❌ Format: `/broadcast <message>`", parse_mode="Markdown")
        return
    text = " ".join(ctx.args)
    all_users = list(users.find())
    sent, failed = 0, 0
    for u in all_users:
        try:
            await ctx.bot.send_message(u["telegramId"], f"📢 *Admin ka message:*\n\n{text}", parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"📢 Broadcast done!\n✅ Sent: {sent}\n❌ Failed: {failed}")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    # Flask ko alag thread mein chalao
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    # Telegram bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("reply",     reply_cmd))
    app.add_handler(CommandHandler("close",     close_cmd))
    app.add_handler(CommandHandler("users",     users_cmd))
    app.add_handler(CommandHandler("sessions",  sessions_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, user_message))

    print("🤖 Bot chal raha hai...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
