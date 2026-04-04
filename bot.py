import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from flask import Flask, request

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN")
ADMIN_ID    = int(os.environ.get("ADMIN_ID", "0"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. https://yourapp.onrender.com
PORT        = int(os.environ.get("PORT", "10000"))

# Active users store
active_users = {}

flask_app = Flask(__name__)

# ─── HANDLERS ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Assalam o Alaikum, {user.first_name}!\n\n"
        "Apna message likh kar bhej dein.\n"
        "Admin jald hi jawab dega. ✅"
    )

async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID:
        return

    active_users[user.id] = {
        "name": user.full_name,
        "username": f"@{user.username}" if user.username else "N/A"
    }

    await update.message.reply_text(
        "✅ Aapka message admin ko bhej diya gaya. Thoda wait karein..."
    )

    keyboard = [[InlineKeyboardButton(
        f"↩️ Reply to {user.full_name}",
        callback_data=f"reply_{user.id}"
    )]]

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📩 *Naya Message*\n\n"
            f"👤 *Naam:* {user.full_name}\n"
            f"🔖 *Username:* {active_users[user.id]['username']}\n"
            f"🆔 *User ID:* `{user.id}`\n\n"
            f"💬 *Message:*\n{update.message.text}"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("Sirf admin reply kar sakta hai.", show_alert=True)
        return

    user_id = int(query.data.split("_")[1])
    name = active_users.get(user_id, {}).get("name", "User")

    context.user_data["replying_to"] = user_id
    context.user_data["replying_name"] = name

    await query.message.reply_text(
        f"✏️ *{name}* ko reply likho:\n_(Cancel: /cancel)_",
        parse_mode="Markdown"
    )

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    target_id = context.user_data.get("replying_to")
    target_name = context.user_data.get("replying_name", "User")

    if not target_id:
        await update.message.reply_text(
            "⚠️ Pehle kisi user ke message ke neeche *↩️ Reply* button dabao.",
            parse_mode="Markdown"
        )
        return

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🛡 *Admin ka Jawab:*\n\n{update.message.text}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Reply *{target_name}* ko bhej di!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

    context.user_data.pop("replying_to", None)
    context.user_data.pop("replying_name", None)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        context.user_data.pop("replying_to", None)
        context.user_data.pop("replying_name", None)
        await update.message.reply_text("❌ Reply cancel ho gayi.")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not active_users:
        await update.message.reply_text("📭 Abhi tak koi user nahi aaya.")
        return
    lines = ["👥 *Active Users:*\n"]
    for uid, info in active_users.items():
        lines.append(f"• {info['name']} ({info['username']}) — `{uid}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── FLASK + WEBHOOK SETUP ────────────────────────────────
ptb_app = None

@flask_app.route("/")
def index():
    return "Bot chal raha hai! ✅"

@flask_app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    import asyncio, json
    from telegram import Update
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    asyncio.run(ptb_app.process_update(update))
    return "OK"

def create_app():
    global ptb_app
    ptb_app = Application.builder().token(BOT_TOKEN).build()

    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CommandHandler("cancel", cancel))
    ptb_app.add_handler(CommandHandler("users", list_users))
    ptb_app.add_handler(CallbackQueryHandler(reply_button, pattern=r"^reply_\d+$"))
    ptb_app.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_ID) & ~filters.COMMAND,
        admin_reply
    ))
    ptb_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        user_message
    ))
    return ptb_app

# ─── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio

    async def setup_webhook():
        app = create_app()
        await app.initialize()
        await app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"
        )
        logger.info(f"Webhook set: {WEBHOOK_URL}/webhook/{BOT_TOKEN}")

    asyncio.run(setup_webhook())
    flask_app.run(host="0.0.0.0", port=PORT)
