import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "YOUR_ADMIN_ID_HERE"))  # Admin ka Telegram numeric ID

# Active conversations: {user_id: {"name": ..., "username": ...}}
active_users = {}

# ─── /start ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Assalam o Alaikum, {user.first_name}!\n\n"
        "Aap apna message likh kar bhej dein.\n"
        "Admin jald hi jawab dega. ✅"
    )

# ─── USER → ADMIN ─────────────────────────────────────────
async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Admin ka apna message ignore karo (woh reply button se bhejta hai)
    if user.id == ADMIN_ID:
        return

    # User register karo
    active_users[user.id] = {
        "name": user.full_name,
        "username": f"@{user.username}" if user.username else "N/A"
    }

    # User ko confirm karo
    await update.message.reply_text("✅ Aapka message admin ko bhej diya gaya. Thoda wait karein...")

    # Admin ko forward karo with reply button
    keyboard = [[InlineKeyboardButton(
        f"↩️ Reply to {user.full_name}",
        callback_data=f"reply_{user.id}"
    )]]
    markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"📩 *Naya Message*\n\n"
        f"👤 *Naam:* {user.full_name}\n"
        f"🔖 *Username:* {active_users[user.id]['username']}\n"
        f"🆔 *User ID:* `{user.id}`\n\n"
        f"💬 *Message:*\n{update.message.text}"
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=markup
    )

# ─── ADMIN REPLY BUTTON ───────────────────────────────────
async def reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("Sirf admin reply kar sakta hai.", show_alert=True)
        return

    user_id = int(query.data.split("_")[1])
    user_info = active_users.get(user_id, {})
    name = user_info.get("name", "User")

    # Admin ka state set karo
    context.user_data["replying_to"] = user_id
    context.user_data["replying_name"] = name

    await query.message.reply_text(
        f"✏️ *{name}* ko reply likho:\n_(Cancel karne ke liye /cancel likho)_",
        parse_mode="Markdown"
    )

# ─── ADMIN MESSAGE → USER ─────────────────────────────────
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    target_id = context.user_data.get("replying_to")
    target_name = context.user_data.get("replying_name", "User")

    if not target_id:
        await update.message.reply_text(
            "⚠️ Pehle kisi user ke message ke neeche *Reply* button dabao.",
            parse_mode="Markdown"
        )
        return

    msg = update.message.text

    # User ko bhejo
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🛡 *Admin ka Jawab:*\n\n{msg}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Reply *{target_name}* ko bhej di!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Message nahi gaya: {e}")

    # State clear karo
    context.user_data.pop("replying_to", None)
    context.user_data.pop("replying_name", None)

# ─── /cancel ──────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        context.user_data.pop("replying_to", None)
        context.user_data.pop("replying_name", None)
        await update.message.reply_text("❌ Reply cancel ho gayi.")

# ─── /users — Admin ke liye active users list ─────────────
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

# ─── MAIN ─────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("users", list_users))
    app.add_handler(CallbackQueryHandler(reply_button, pattern=r"^reply_\d+$"))

    # Admin reply (text, lekin "replying_to" set ho)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_ID) & ~filters.COMMAND,
        admin_reply
    ))

    # User messages
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        user_message
    ))

    logger.info("Bot chal raha hai...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
