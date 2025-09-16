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

# ---------------- ADMIN PANEL ----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    buttons = [
        [KeyboardButton("➕ Add Product"), KeyboardButton("❌ Delete Product")],
        [KeyboardButton("💳 Add Payment Method"), KeyboardButton("🧾 List Payments")],
        [KeyboardButton("📦 Pending Orders"), KeyboardButton("📊 All Orders")],
        [KeyboardButton("☑️ Complete Order")],
        [KeyboardButton("🚫 Ban User"), KeyboardButton("✅ Unban User")],
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("⚙️ Admin Panel:", reply_markup=reply_markup)

# --- Add Product (step by step) ---
ADD_TITLE, ADD_PRICE, ADD_DESC, CONFIRM = range(4)
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter product title:")
    return ADD_TITLE
async def add_product_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"] = {"title": update.message.text}
    await update.message.reply_text("Enter price:")
    return ADD_PRICE
async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"]["price"] = update.message.text
    await update.message.reply_text("Enter description:")
    return ADD_DESC
async def add_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"]["desc"] = update.message.text
    product = context.user_data["new_product"]
    await update.message.reply_text(
        f"Confirm product:\n{product['title']} - ₹{product['price']}\n{product['desc']}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm", callback_data="confirm_add")]])
    )
    return CONFIRM
async def confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product = context.user_data["new_product"]
    products.append(product)
    await query.edit_message_text("✅ Product added successfully!")
    return ConversationHandler.END

# --- Add Payment (step by step) ---
PAY_NAME, PAY_DETAILS, PAY_CONFIRM = range(5,8)
async def add_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter payment method name (e.g. UPI, Bank):")
    return PAY_NAME
async def add_payment_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_payment"] = {"method": update.message.text}
    await update.message.reply_text("Enter payment details/UPI ID:")
    return PAY_DETAILS
async def add_payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_payment"]["details"] = update.message.text
    p = context.user_data["new_payment"]
    await update.message.reply_text(
        f"Confirm payment method:\n{p['method']} - {p['details']}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm", callback_data="confirm_payment")]])
    )
    return PAY_CONFIRM
async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payment = context.user_data["new_payment"]
    payments.append(payment)
    await query.edit_message_text("✅ Payment method added!")
    return ConversationHandler.END

# --- Delete Product ---
async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not products:
        await update.message.reply_text("No products to delete.")
        return
    keyboard = [[InlineKeyboardButton(p["title"], callback_data=f"delprod_{i}")]
                for i, p in enumerate(products)]
    await update.message.reply_text("Select product to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
async def confirm_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("_")[1])
    prod = products.pop(index)
    await query.edit_message_text(f"❌ Deleted product: {prod['title']}")

# --- List Payments ---
async def list_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not payments:
        await update.message.reply_text("No payments added.")
        return
    text = "💳 Payment Methods:\n\n"
    for p in payments:
        text += f"- {p['method']}: {p['details']}\n"
    await update.message.reply_text(text)

# --- Pending Orders ---
async def pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = [o for o in orders if o["status"] == "pending"]
    if not pending:
        await update.message.reply_text("No pending orders.")
        return
    text = "📦 Pending Orders:\n\n"
    for o in pending:
        text += f"#{o['id']} - {o['product']['title']} (User: {o['user_id']})\n"
    await update.message.reply_text(text)

# --- All Orders ---
async def all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not orders:
        await update.message.reply_text("No orders yet.")
        return
    text = "📊 All Orders:\n\n"
    for o in orders:
        text += f"#{o['id']} - {o['product']['title']} | {o['status']} (User: {o['user_id']})\n"
    await update.message.reply_text(text)

# --- Complete Order ---
async def complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = [o for o in orders if o["status"] == "pending"]
    if not pending:
        await update.message.reply_text("No pending orders to complete.")
        return
    keyboard = [[InlineKeyboardButton(f"#{o['id']} - {o['product']['title']}", callback_data=f"done_{o['id']}")]
                for o in pending]
    await update.message.reply_text("Select order to complete:", reply_markup=InlineKeyboardMarkup(keyboard))
async def confirm_complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    oid = int(query.data.split("_")[1])
    for o in orders:
        if o["id"] == oid:
            o["status"] = "completed"
            await query.edit_message_text(f"☑️ Order #{oid} marked as completed.")
            await context.bot.send_message(chat_id=o["user_id"], text=f"✅ Your order #{oid} has been completed!")
            break

# --- Ban/Unban ---
BAN, UNBAN = range(9,11)
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter User ID to ban:")
    return BAN
async def ban_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = int(update.message.text)
    banned_users.add(uid)
    await update.message.reply_text(f"🚫 User {uid} banned.")
    return ConversationHandler.END
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter User ID to unban:")
    return UNBAN
async def unban_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = int(update.message.text)
    banned_users.discard(uid)
    await update.message.reply_text(f"✅ User {uid} unbanned.")
    return ConversationHandler.END

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

    conv_add_product = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ Add Product"), add_product_start)],
        states={
            ADD_TITLE: [MessageHandler(filters.TEXT, add_product_title)],
            ADD_PRICE: [MessageHandler(filters.TEXT, add_product_price)],
            ADD_DESC: [MessageHandler(filters.TEXT, add_product_desc)],
            CONFIRM: [CallbackQueryHandler(confirm_add, pattern="^confirm_add$")],
        },
        fallbacks=[]
    )
    conv_add_payment = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("💳 Add Payment Method"), add_payment_start)],
        states={
            PAY_NAME: [MessageHandler(filters.TEXT, add_payment_name)],
            PAY_DETAILS: [MessageHandler(filters.TEXT, add_payment_details)],
            PAY_CONFIRM: [CallbackQueryHandler(confirm_payment, pattern="^confirm_payment$")],
        },
        fallbacks=[]
    )
    conv_ban = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🚫 Ban User"), ban_user)],
        states={BAN: [MessageHandler(filters.TEXT, ban_user_confirm)]},
        fallbacks=[]
    )
    conv_unban = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("✅ Unban User"), unban_user)],
        states={UNBAN: [MessageHandler(filters.TEXT, unban_user_confirm)]},
        fallbacks=[]
    )

    app.add_handler(conv_add_product)
    app.add_handler(conv_add_payment)
    app.add_handler(conv_ban)
    app.add_handler(conv_unban)

    app.add_handler(MessageHandler(filters.Regex("❌ Delete Product"), delete_product))
    app.add_handler(CallbackQueryHandler(confirm_delete_product, pattern="^delprod_"))
    app.add_handler(MessageHandler(filters.Regex("🧾 List Payments"), list_payments))
    app.add_handler(MessageHandler(filters.Regex("📦 Pending Orders"), pending_orders))
    app.add_handler(MessageHandler(filters.Regex("📊 All Orders"), all_orders))
    app.add_handler(MessageHandler(filters.Regex("☑️ Complete Order"), complete_order))
    app.add_handler(CallbackQueryHandler(confirm_complete_order, pattern="^done_"))

    print("✅ Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
