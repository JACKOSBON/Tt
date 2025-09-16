import logging
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# ---------------- CONFIG ----------------
BOT_TOKEN = "8291608976:AAEeii9LVk-fIGN9nkR7_7gBNPB-fhEDmjM"
ADMIN_ID = 7715257236  # apna telegram numeric id daalo

# ---------------- DATA STORAGE ----------------
products = []
payments = []
orders = []
banned_users = set()

# ---------------- LOGGER ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


# ---------------- USER PANEL ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in banned_users:
        await update.message.reply_text("🚫 You are banned from this shop.")
        return

    buttons = [
        [KeyboardButton("🛒 Catalog")],
        [KeyboardButton("📦 My Orders")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("⚙️ Admin Panel")])

    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("Welcome! Please choose:", reply_markup=reply_markup)


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not products:
        await update.message.reply_text("No products available.")
        return
    keyboard = [[InlineKeyboardButton(f"{p['title']} - ₹{p['price']}", callback_data=f"buy_{i}")]
                for i, p in enumerate(products)]
    await update.message.reply_text("🛒 Catalog:", reply_markup=InlineKeyboardMarkup(keyboard))


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_orders = [o for o in orders if o["user_id"] == user_id]
    if not user_orders:
        await update.message.reply_text("You have no orders.")
        return
    text = "📦 Your Orders:\n\n"
    for o in user_orders:
        text += f"- {o['product']['title']} | Status: {o['status']}\n"
    await update.message.reply_text(text)


# ---------------- ORDER FLOW ----------------
async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("_")[1])
    context.user_data["product"] = products[index]

    if not payments:
        await query.edit_message_text("No payment methods available. Try later.")
        return

    keyboard = [[InlineKeyboardButton(p["method"], callback_data=f"pay_{i}")]
                for i, p in enumerate(payments)]
    await query.edit_message_text("💳 Choose payment method:", reply_markup=InlineKeyboardMarkup(keyboard))


async def select_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("_")[1])
    payment = payments[index]
    context.user_data["payment"] = payment

    await query.edit_message_text(
        f"Pay using {payment['method']}:\n{payment['details']}\n\n"
        "➡️ Now send payment screenshot and YouTube/link together."
    )
    context.user_data["awaiting_payment"] = True


async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_payment"):
        return
    user_id = update.effective_user.id
    product = context.user_data["product"]
    payment = context.user_data["payment"]

    screenshot = None
    if update.message.photo:
        screenshot = update.message.photo[-1].file_id
    link = update.message.caption if update.message.caption else update.message.text

    order = {
        "id": len(orders) + 1,
        "user_id": user_id,
        "product": product,
        "payment": payment,
        "screenshot": screenshot,
        "link": link,
        "status": "pending"
    }
    orders.append(order)
    context.user_data["awaiting_payment"] = False

    await update.message.reply_text("✅ Order placed! Wait for admin confirmation.")

    text = (f"📢 New Order #{order['id']}:\nUser: {user_id}\nProduct: {product['title']}\n"
            f"Payment: {payment['method']}\nLink: {link}\nStatus: pending")
    if screenshot:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=screenshot, caption=text)
    else:
        await context.bot.send_message(chat_id=ADMIN_ID, text=text)


# ---------------- ADMIN PANEL (INLINE BUTTONS) ----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add_product")],
        [InlineKeyboardButton("❌ Delete Product", callback_data="admin_delete_product")],
        [InlineKeyboardButton("💳 Add Payment", callback_data="admin_add_payment")],
        [InlineKeyboardButton("🧾 List Payments", callback_data="admin_list_payments")],
        [InlineKeyboardButton("📦 Pending Orders", callback_data="admin_pending")],
        [InlineKeyboardButton("📊 All Orders", callback_data="admin_all")],
        [InlineKeyboardButton("☑️ Complete Order", callback_data="admin_complete")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
    ]
    await update.message.reply_text("⚙️ Admin Panel:", reply_markup=InlineKeyboardMarkup(keyboard))


# Example: Add Product
async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin_add_product":
        await query.edit_message_text("Send product in format:\nTitle | Price | Description")
        context.user_data["awaiting_product"] = True

    elif query.data == "admin_list_payments":
        if not payments:
            await query.edit_message_text("No payments added.")
        else:
            txt = "💳 Payment Methods:\n\n"
            for p in payments:
                txt += f"- {p['method']}: {p['details']}\n"
            await query.edit_message_text(txt)

    elif query.data == "admin_pending":
        pending = [o for o in orders if o["status"] == "pending"]
        if not pending:
            await query.edit_message_text("No pending orders.")
        else:
            txt = "📦 Pending Orders:\n\n"
            for o in pending:
                txt += f"#{o['id']} - {o['product']['title']} (User: {o['user_id']})\n"
            await query.edit_message_text(txt)

    elif query.data == "admin_all":
        if not orders:
            await query.edit_message_text("No orders yet.")
        else:
            txt = "📊 All Orders:\n\n"
            for o in orders:
                txt += f"#{o['id']} - {o['product']['title']} | {o['status']} (User: {o['user_id']})\n"
            await query.edit_message_text(txt)


# Handle product add via text
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_product"):
        try:
            title, price, desc = update.message.text.split("|")
            product = {"title": title.strip(), "price": price.strip(), "desc": desc.strip()}
            products.append(product)
            await update.message.reply_text(f"✅ Product added: {title}")
        except:
            await update.message.reply_text("❌ Wrong format. Use: Title | Price | Description")
        context.user_data["awaiting_product"] = False


# ---------------- MAIN ----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # User
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("🛒 Catalog"), show_catalog))
    app.add_handler(MessageHandler(filters.Regex("📦 My Orders"), my_orders))
    app.add_handler(CallbackQueryHandler(buy_product, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(select_payment, pattern="^pay_"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT, receive_screenshot))

    # Admin
    app.add_handler(MessageHandler(filters.Regex("⚙️ Admin Panel"), admin_panel))
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT, admin_text_handler))

    print("✅ Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()