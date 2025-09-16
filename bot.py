"""
Telegram Shop Bot with Admin Panel
Features:
- Catalog browsing
- Order placement with payment proof + social link
- Admin panel (add product, add payment, ban/unban users, manage orders)
"""

import os
import json
import time
from typing import Dict, Any

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters
)

# ============ CONFIG ============
BOT_TOKEN = "8291608976:AAEeii9LVk-fIGN9nkR7_7gBNPB-fhEDmjM""   # Replace with your bot token
ADMIN_ID = 7715257236                # Replace with your Telegram user ID
DATA_FILE = "data.json"
# ================================

# States
(ADD_PROD_NAME, ADD_PROD_PRICE, ADD_PROD_DESC, ADD_PROD_PHOTO,
 ADD_PAY_LABEL, ADD_PAY_TYPE, AWAIT_PAYMENT_PROOF, AWAIT_SOCIAL_LINK) = range(8)

DEFAULT_DATA = {
    "products": [],
    "payments": [],
    "orders": [],
    "banned": [],
    "next_product_id": 1,
    "next_payment_id": 1,
    "next_order_id": 1,
}

# ========== Helpers ==========
def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_DATA, f, indent=2)
        return DEFAULT_DATA.copy()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data: Dict[str, Any]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

async def is_admin(user_id: int) -> bool:
    return int(user_id) == int(ADMIN_ID)

# ========== User Commands ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    if user.id in data.get("banned", []):
        await update.message.reply_text("🚫 Aap banned hain.")
        return

    kb = [[InlineKeyboardButton("🛍 Show Catalog", callback_data="catalog")]]
    if await is_admin(user.id):
        kb.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])

    await update.message.reply_text(
        f"Hello {user.first_name}! Welcome to the Shop Bot.",
        reply_markup=InlineKeyboardMarkup(kb),
    )

# ========== Catalog ==========
async def catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    products = data.get("products", [])
    if not products:
        await query.message.reply_text("Catalog is empty.")
        return
    for prod in products:
        kb = [[InlineKeyboardButton("Buy", callback_data=f"buy_{prod['id']}")]]
        text = f"📦 {prod['name']}\n💰 Price: {prod['price']}\n📝 {prod['desc']}"
        if prod.get("photo"):
            await query.message.reply_photo(prod["photo"], caption=text,
                                            reply_markup=InlineKeyboardMarkup(kb))
        else:
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_", 1)[1])
    data = load_data()
    prod = next((p for p in data["products"] if p["id"] == pid), None)
    if not prod:
        await query.message.reply_text("❌ Product not found.")
        return
    context.user_data["buy_product"] = prod
    kb = [[InlineKeyboardButton(p["label"], callback_data=f"pay_{p['id']}")]
          for p in data.get("payments", [])]
    if not kb:
        await query.message.reply_text("⚠️ No payment methods available.")
        return
    await query.message.reply_text("Choose payment method:", reply_markup=InlineKeyboardMarkup(kb))

# ========== Buy Flow ==========
async def pay_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pay_id = int(query.data.split("_", 1)[1])
    data = load_data()
    pay = next((p for p in data["payments"] if p["id"] == pay_id), None)
    if not pay:
        await query.message.reply_text("❌ Payment method not found.")
        return
    context.user_data["selected_payment"] = pay
    if pay["type"] == "upi":
        await query.message.reply_text(f"Send payment to:\n`{pay['content']}`\n\n📸 Then upload payment screenshot.",
                                       parse_mode="Markdown")
    else:
        await query.message.reply_photo(pay["content"], caption="Scan QR & pay, then upload screenshot.")
    return AWAIT_PAYMENT_PROOF

async def receive_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Please send photo proof.")
        return AWAIT_PAYMENT_PROOF
    context.user_data["payment_proof"] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ Payment proof received.\nNow send a link (YouTube/Instagram/Channel):")
    return AWAIT_SOCIAL_LINK

async def receive_social_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    user = update.effective_user
    data = load_data()
    prod = context.user_data.get("buy_product")
    pay = context.user_data.get("selected_payment")
    proof = context.user_data.get("payment_proof")

    if not prod or not pay or not proof:
        await update.message.reply_text("⚠️ Session expired. Start again.")
        return ConversationHandler.END

    oid = data["next_order_id"]
    order = {
        "id": oid, "user_id": user.id,
        "product_id": prod["id"], "status": "pending",
        "payment_id": pay["id"], "proof_file_id": proof,
        "link": link, "ts": int(time.time())
    }
    data["orders"].append(order)
    data["next_order_id"] = oid + 1
    save_data(data)

    await update.message.reply_text("✅ Order placed. Admin will review it.")
    caption = (f"🆕 Order #{order['id']}\n👤 User: {user.full_name} (id:{user.id})\n"
               f"📦 Product: {prod['name']}\n💳 Payment: {pay['label']}\n🔗 Link: {link}\n📌 Status: pending")
    kb = [[InlineKeyboardButton("✅ Mark Complete", callback_data=f"complete_{oid}")],
          [InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_{user.id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=proof, caption=caption,
                                 reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ========== Admin Panel ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("➕ Add Product", callback_data="add_product")],
        [InlineKeyboardButton("💳 Add Payment", callback_data="add_payment")],
        [InlineKeyboardButton("📋 All Orders", callback_data="all_orders")],
        [InlineKeyboardButton("⏳ Pending Orders", callback_data="pending_orders")],
        [InlineKeyboardButton("✅ Completed Orders", callback_data="completed_orders")],
        [InlineKeyboardButton("🙅 Banned Users", callback_data="banned_users")],
    ]
    await query.message.reply_text("⚙️ Admin Panel:", reply_markup=InlineKeyboardMarkup(kb))

# ---- Admin: Manage Orders ----
async def complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    oid = int(query.data.split("_", 1)[1])
    data = load_data()
    order = next((o for o in data["orders"] if o["id"] == oid), None)
    if not order:
        await query.message.reply_text("❌ Order not found.")
        return
    order["status"] = "completed"
    save_data(data)
    try:
        await context.bot.send_message(order["user_id"], f"✅ Your order #{oid} has been marked completed by Admin.")
    except:
        pass
    await query.message.reply_text(f"✅ Order #{oid} marked as completed.")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_", 1)[1])
    data = load_data()
    if uid not in data["banned"]:
        data["banned"].append(uid)
        save_data(data)
    await query.message.reply_text(f"🚫 User {uid} banned.")

async def show_banned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    banned = data.get("banned", [])
    if not banned:
        await query.message.reply_text("✅ No banned users.")
        return
    for uid in banned:
        kb = [[InlineKeyboardButton("Unban", callback_data=f"unban_{uid}")]]
        await query.message.reply_text(f"🚫 User ID: {uid}", reply_markup=InlineKeyboardMarkup(kb))

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_", 1)[1])
    data = load_data()
    if uid in data["banned"]:
        data["banned"].remove(uid)
        save_data(data)
    await query.message.reply_text(f"✅ User {uid} unbanned.")

# ---- Admin: Orders ----
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE, status=None):
    query = update.callback_query
    await query.answer()
    data = load_data()
    orders = data["orders"]
    if status:
        orders = [o for o in orders if o["status"] == status]
    if not orders:
        await query.message.reply_text("No orders found.")
        return
    for o in orders:
        prod = next((p for p in data["products"] if p["id"] == o["product_id"]), None)
        caption = (f"📦 Order #{o['id']} ({o['status']})\n👤 User id: {o['user_id']}\n"
                   f"Product: {prod['name'] if prod else 'unknown'}\n🔗 Link: {o.get('link','-')}")
        kb = []
        if o["status"] == "pending":
            kb = [[InlineKeyboardButton("✅ Mark Complete", callback_data=f"complete_{o['id']}"),
                   InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_{o['user_id']}")]]
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=o["proof_file_id"], caption=caption,
                                     reply_markup=InlineKeyboardMarkup(kb) if kb else None)

# ========== Main ==========
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))

    # Catalog
    app.add_handler(CallbackQueryHandler(catalog_callback, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(pay_selected, pattern="^pay_"))

    # Admin Panel
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(lambda u,c: show_orders(u,c), pattern="^all_orders$"))
    app.add_handler(CallbackQueryHandler(lambda u,c: show_orders(u,c,'pending'), pattern="^pending_orders$"))
    app.add_handler(CallbackQueryHandler(lambda u,c: show_orders(u,c,'completed'), pattern="^completed_orders$"))
    app.add_handler(CallbackQueryHandler(show_banned, pattern="^banned_users$"))
    app.add_handler(CallbackQueryHandler(unban_user, pattern="^unban_"))
    app.add_handler(CallbackQueryHandler(complete_order, pattern="^complete_"))
    app.add_handler(CallbackQueryHandler(ban_user, pattern="^ban_"))

    # Conversations (Add product, Add payment, Buy flow)
    conv_prod = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u,c: None, pattern="^add_product$")],
        states={
            ADD_PROD_NAME: [MessageHandler(filters.TEXT, product_name)],
            ADD_PROD_PRICE: [MessageHandler(filters.TEXT, product_price)],
            ADD_PROD_DESC: [MessageHandler(filters.TEXT, product_desc)],
            ADD_PROD_PHOTO: [MessageHandler(filters.PHOTO, product_photo)],
        },
        fallbacks=[]
    )
    app.add_handler(conv_prod)

    conv_pay = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u,c: None, pattern="^add_payment$")],
        states={
            ADD_PAY_LABEL: [MessageHandler(filters.TEXT, payment_label)],
            ADD_PAY_TYPE: [MessageHandler(filters.TEXT, payment_type),
                           MessageHandler(filters.PHOTO, payment_content)],
        },
        fallbacks=[]
    )
    app.add_handler(conv_pay)

    conv_buy = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_payment_proof)],
        states={
            AWAIT_PAYMENT_PROOF: [MessageHandler(filters.PHOTO, receive_payment_proof)],
            AWAIT_SOCIAL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_social_link)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_buy)

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
