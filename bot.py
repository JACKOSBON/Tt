# -*- coding: utf-8 -*-

import logging
import json
import os
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputFile, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Logging setup, console me bot ki activities dekhne ke liye
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Apna Telegram Bot Token yahan daalein
BOT_TOKEN = "8291608976:AAEeii9LVk-fIGN9nkR7_7gBNPB-fhEDmjM" 
# Apni Telegram User ID yahan daalein (ek number hoga)
ADMIN_ID = 7715257236  # Replace with your actual Telegram User ID

# --- DATA FILES ---
PRODUCTS_FILE = 'products.json'
ORDERS_FILE = 'orders.json'
BANNED_USERS_FILE = 'banned_users.json'
CONFIG_FILE = 'config.json'

# --- HELPER FUNCTIONS FOR DATA HANDLING ---

def load_data(filename, default_data=None):
    """JSON file se data load karne ke liye function."""
    if default_data is None:
        default_data = {}
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            json.dump(default_data, f, indent=4)
        return default_data
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_data

def save_data(filename, data):
    """Data ko JSON file me save karne ke liye function."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

# Initial data load
products_data = load_data(PRODUCTS_FILE, {"products": []})
orders_data = load_data(ORDERS_FILE, {"orders": []})
banned_users = load_data(BANNED_USERS_FILE, {"banned_ids": []})
config_data = load_data(CONFIG_FILE, {"upi_id": "AapkiUPI@ybl", "qr_code_id": None})


# --- ADMIN CHECK DECORATOR ---
def admin_only(func):
    """Function ko sirf admin ke liye restrict karne wala decorator."""
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ Aapke paas is command ka access nahi hai.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- USER COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User ke liye welcome message aur menu."""
    user = update.effective_user
    user_id = user.id

    if user_id in banned_users['banned_ids']:
        await update.message.reply_text("❌ Aapko is bot se ban kar diya gaya hai.")
        return

    keyboard = [
        [InlineKeyboardButton("🛍️ Products Dekhein", callback_data="view_products")],
        [InlineKeyboardButton("📞 Humse Sampark Karein", callback_data="contact_us")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = f"Namaste {user.mention_html()}!\n Aapka hamare shop bot mein swagat hai."
    
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
        welcome_text += "\n\nAap admin hain. Admin panel access karne ke liye neeche button par click karein."

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')


# --- ADMIN PANEL & COMMANDS ---
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin ke liye control panel."""
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("➕ Product Add Karein", callback_data="add_product"),
            InlineKeyboardButton("🗑️ Product Delete Karein", callback_data="delete_product_list")
        ],
        [
            InlineKeyboardButton("📋 Pending Orders", callback_data="view_orders_pending"),
            InlineKeyboardButton("✅ Completed Orders", callback_data="view_orders_completed")
        ],
        [
            InlineKeyboardButton("📊 Order Stats", callback_data="order_stats"),
            InlineKeyboardButton("⚙️ Payment Settings", callback_data="payment_settings")
        ],
        [
            InlineKeyboardButton("🚫 User Ban Karein", callback_data="ban_user_prompt"),
            InlineKeyboardButton("🔓 User Unban Karein", callback_data="unban_user_prompt")
        ],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "👑 Admin Panel\nYahan se aap bot ko manage kar sakte hain."
    
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

# --- CONVERSATION HANDLER FOR ADDING PRODUCT ---
NAME, DESCRIPTION, PRICE, PHOTO = range(4)

async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Product add karne ka process shuru karega."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Kripya product ka naam batayein:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Product ka naam store karega."""
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Ab product ka description batayein:")
    return DESCRIPTION

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Product ka description store karega."""
    context.user_data['description'] = update.message.text
    await update.message.reply_text("Ab product ka price batayein (sirf number, jaise: 199):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Product ka price store karega."""
    try:
        price = float(update.message.text)
        context.user_data['price'] = price
        await update.message.reply_text("Ab product ka photo bhejein:")
        return PHOTO
    except ValueError:
        await update.message.reply_text("Galat format. Kripya sirf number enter karein (jaise: 199).")
        return PRICE

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Product ka photo store karega aur product save karega."""
    photo_file = await update.message.photo[-1].get_file()
    
    # Generate unique product ID
    product_id = len(products_data['products']) + 1
    
    new_product = {
        'id': product_id,
        'name': context.user_data['name'],
        'description': context.user_data['description'],
        'price': context.user_data['price'],
        'photo_id': photo_file.file_id  # Store file_id to resend photo
    }
    
    products_data['products'].append(new_product)
    save_data(PRODUCTS_FILE, products_data)
    
    await update.message.reply_text("✅ Product safaltapoorvak add ho gaya hai!")
    
    # Admin panel dobara dikhayein
    await admin_panel(update, context)
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Conversation ko cancel karega."""
    await update.message.reply_text("Process cancel kar diya gaya hai.")
    context.user_data.clear()
    await admin_panel(update, context) # Admin panel pe wapas bhej dega
    return ConversationHandler.END

# --- OTHER ADMIN FUNCTIONS ---

async def show_delete_product_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete karne ke liye products ki list dikhayega."""
    query = update.callback_query
    await query.answer()
    
    products = products_data['products']
    if not products:
        await query.edit_message_text("Abhi koi product nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))
        return

    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(f"❌ {product['name']} (₹{product['price']})", callback_data=f"delete_prod_{product['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])
    
    await query.edit_message_text("Aap kaunsa product delete karna chahte hain?", reply_markup=InlineKeyboardMarkup(keyboard))

async def view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE, status_filter: str):
    """Orders ko status ke hisaab se dikhayega."""
    query = update.callback_query
    await query.answer()

    filtered_orders = [order for order in orders_data['orders'] if order['status'] == status_filter]

    if not filtered_orders:
        await query.edit_message_text(f"Koi {status_filter} order nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))
        return
    
    await query.edit_message_text(f"--- {status_filter.upper()} Orders ---")

    for order in filtered_orders:
        user_info = f"User ID: {order['user_id']} ({order.get('username', 'N/A')})"
        product_info = f"Product: {order['product_name']} (₹{order['product_price']})"
        order_time = f"Time: {order['timestamp']}"
        text = f"📄 Order #{order['order_id']}\n👤 {user_info}\n🛍️ {product_info}\n🕒 {order_time}"
        
        keyboard = []
        if status_filter == 'pending':
            keyboard.append([InlineKeyboardButton("✅ Mark as Complete", callback_data=f"complete_order_{order['order_id']}")])

        await context.bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
    
    # Back to admin panel button
    await context.bot.send_message(chat_id=ADMIN_ID, text="Orders list samapt.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))

async def order_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Total aur pending orders ka count dikhayega."""
    query = update.callback_query
    await query.answer()
    
    total_orders = len(orders_data['orders'])
    pending_orders = len([o for o in orders_data['orders'] if o['status'] == 'pending'])
    completed_orders = total_orders - pending_orders
    
    stats_text = (
        "📊 Order Statistics 📊\n\n"
        f"- Kul Orders: {total_orders}\n"
        f"- Pending Orders: {pending_orders}\n"
        f"- Completed Orders: {completed_orders}"
    )
    
    await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))


# --- USER-FACING PRODUCT & ORDERING ---

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Users ko products dikhayega."""
    query = update.callback_query
    await query.answer()

    products = products_data['products']
    if not products:
        await query.edit_message_text("Maaf kijiye, abhi koi product available nahi hai.")
        return

    await query.message.reply_text("Hamare products neeche diye gaye hain:")

    for product in products:
        caption = f"<b>{product['name']}</b>\n\n{product['description']}\n\n<b>Price: ₹{product['price']}</b>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Abhi Khareedein", callback_data=f"buy_{product['id']}")]
        ])
        await context.bot.send_photo(chat_id=query.from_user.id, photo=product['photo_id'], caption=caption, reply_markup=keyboard, parse_mode='HTML')


# --- PAYMENT SETTINGS ---
SET_UPI, SET_QR = range(2)

async def payment_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    current_upi = config_data.get('upi_id', 'Not Set')
    qr_status = "Set" if config_data.get('qr_code_id') else "Not Set"
    
    text = (
        f"⚙️ Payment Settings\n\n"
        f"Current UPI ID: `{current_upi}`\n"
        f"QR Code Status: {qr_status}"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ UPI ID Edit Karein", callback_data="edit_upi")],
        [InlineKeyboardButton("🖼️ QR Code Set/Update Karein", callback_data="edit_qr")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def edit_upi_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Nayi UPI ID bhejein:")
    return SET_UPI

async def set_upi_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_upi_id = update.message.text
    config_data['upi_id'] = new_upi_id
    save_data(CONFIG_FILE, config_data)
    await update.message.reply_text(f"✅ UPI ID safaltapoorvak `{new_upi_id}` par set ho gayi hai.", parse_mode='Markdown')
    await admin_panel(update, context)
    return ConversationHandler.END
    
async def edit_qr_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Naya QR Code ka photo bhejein:")
    return SET_QR

async def set_qr_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file_id = update.message.photo[-1].file_id
    config_data['qr_code_id'] = photo_file_id
    save_data(CONFIG_FILE, config_data)
    await update.message.reply_text("✅ QR Code safaltapoorvak set ho gaya hai.")
    await admin_panel(update, context)
    return ConversationHandler.END

# --- BAN/UNBAN ---
BAN_ID, UNBAN_ID = range(2)

async def ban_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Jis user ko ban karna hai, uski User ID bhejein.")
    return BAN_ID

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id_to_ban = int(update.message.text)
        if user_id_to_ban == ADMIN_ID:
            await update.message.reply_text("Aap khud ko ban nahi kar sakte.")
        elif user_id_to_ban not in banned_users['banned_ids']:
            banned_users['banned_ids'].append(user_id_to_ban)
            save_data(BANNED_USERS_FILE, banned_users)
            await update.message.reply_text(f"✅ User ID {user_id_to_ban} ko ban kar diya gaya hai.")
        else:
            await update.message.reply_text(f"User ID {user_id_to_ban} pehle se hi banned hai.")
    except ValueError:
        await update.message.reply_text("Yeh ek valid User ID nahi hai.")

    await admin_panel(update, context)
    return ConversationHandler.END

async def unban_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if not banned_users['banned_ids']:
        await query.message.reply_text("Abhi koi user banned nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))
        return ConversationHandler.END

    await query.message.reply_text("Jis user ko unban karna hai, uski User ID bhejein.")
    return UNBAN_ID

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id_to_unban = int(update.message.text)
        if user_id_to_unban in banned_users['banned_ids']:
            banned_users['banned_ids'].remove(user_id_to_unban)
            save_data(BANNED_USERS_FILE, banned_users)
            await update.message.reply_text(f"✅ User ID {user_id_to_unban} ko unban kar diya gaya hai.")
        else:
            await update.message.reply_text(f"User ID {user_id_to_unban} banned list mein nahi hai.")
    except ValueError:
        await update.message.reply_text("Yeh ek valid User ID nahi hai.")

    await admin_panel(update, context)
    return ConversationHandler.END
    
# --- CALLBACK QUERY HANDLER ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sabhi inline buttons ke actions ko handle karega."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if user_id in banned_users['banned_ids']:
        await query.message.reply_text("❌ Aapko is bot se ban kar diya gaya hai.")
        return

    # User-side buttons
    if data == "view_products":
        await show_products(update, context)
    elif data == "contact_us":
        await query.message.reply_text("Aap admin se @username par sampark kar sakte hain.") # Admin ka username yahan daalein
    elif data.startswith("buy_"):
        product_id = int(data.split("_")[1])
        product = next((p for p in products_data['products'] if p['id'] == product_id), None)
        
        if product:
            text = f"Aapne chuna hai: <b>{product['name']}</b>\nPrice: ₹{product['price']}\n\nPayment karne ke liye 'Confirm Karein' par click karein."
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Karein", callback_data=f"confirm_{product_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="view_products")]
            ])
            # Use edit_message_media to replace the photo and caption smoothly
            media = InputMediaPhoto(media=product['photo_id'], caption=text, parse_mode='HTML')
            await query.edit_message_media(media=media, reply_markup=keyboard)

    elif data.startswith("confirm_"):
        product_id = int(data.split("_")[1])
        product = next((p for p in products_data['products'] if p['id'] == product_id), None)
        
        if product:
            payment_text = (
                f"Kripya neeche di gayi details par ₹{product['price']} ka payment karein:\n\n"
                f"<b>UPI ID:</b> `{config_data['upi_id']}`\n\n"
                "Payment karne ke baad, kripya transaction ID ya screenshot isi chat mein bhejein. "
                "Aapka order 'pending' mark kar diya gaya hai aur admin jald hi confirm karenge."
            )
            await query.message.reply_text(payment_text, parse_mode='HTML')
            
            # Send QR code if available
            if config_data.get('qr_code_id'):
                await context.bot.send_photo(chat_id=user_id, photo=config_data['qr_code_id'], caption="Aap is QR code ko scan karke bhi payment kar sakte hain.")

            # Create a new order
            order_id = len(orders_data['orders']) + 1
            new_order = {
                'order_id': order_id,
                'user_id': user_id,
                'username': query.from_user.username or query.from_user.first_name,
                'product_id': product_id,
                'product_name': product['name'],
                'product_price': product['price'],
                'status': 'pending',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            orders_data['orders'].append(new_order)
            save_data(ORDERS_FILE, orders_data)
            
            # Notify Admin
            admin_notification = (
                f"🔔 Naya Order Aaya Hai! (Order #{order_id})\n\n"
                f"<b>User:</b> {query.from_user.mention_html()} (ID: `{user_id}`)\n"
                f"<b>Product:</b> {product['name']}\n"
                f"<b>Price:</b> ₹{product['price']}\n\n"
                "User payment proof bhejega. Kripya order ko verify karke complete karein."
            )
            admin_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Order Complete Karein", callback_data=f"complete_order_{order_id}")],
                 [InlineKeyboardButton("🚫 Is User ko Ban Karein", callback_data=f"ban_user_{user_id}")]
            ])
            await context.bot.send_message(chat_id=ADMIN_ID, 