import os
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from pymongo import MongoClient

# -------- ENV VARIABLES --------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS").split(",")]

# -------- DB CONNECT --------
client = MongoClient(MONGO_URL)
db = client["chatbot"]
users = db["users"]

# -------- APP --------
app = Flask(__name__)
tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

# -------- FUNCTIONS --------
def save_user(user_id):
    if not users.find_one({"user_id": user_id}):
        users.insert_one({"user_id": user_id})

def get_all_users():
    return users.find()

# -------- USER MESSAGE --------
async def user_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id

    save_user(user_id)

    for admin in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin,
            text=f"👤 {user.first_name} ({user_id}):\n{update.message.text}"
        )

# -------- ADMIN REPLY --------
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        try:
            text = update.message.reply_to_message.text
            user_id = int(text.split("(")[1].split(")")[0])

            await context.bot.send_message(
                chat_id=user_id,
                text=f"💬 Admin: {update.message.text}"
            )
        except:
            await update.message.reply_text("❌ Error in reply")

# -------- BROADCAST --------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        return

    msg = " ".join(context.args)
    count = 0

    for user in get_all_users():
        try:
            await context.bot.send_message(chat_id=user["user_id"], text=msg)
            count += 1
        except:
            pass

    await update.message.reply_text(f"✅ Sent to {count} users")

# -------- START --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.message.from_user.id)
    await update.message.reply_text("✅ Bot started! Send message to contact admin.")

# -------- HANDLERS --------
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("broadcast", broadcast))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.User(ADMIN_IDS), user_msg))
tg_app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), admin_reply))

# -------- WEBHOOK --------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), tg_app.bot)
    await tg_app.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "Bot running!"

# -------- RUN --------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=PORT)
