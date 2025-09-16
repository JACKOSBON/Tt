import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import asyncio

# Bot Configuration - आपकी bot token यहां डालें
BOT_TOKEN = "8291608976:AAEeii9LVk-fIGN9nkR7_7gBNPB-fhEDmjM"  # BotFather से मिली token यहां डालें
ADMIN_ID = 7715257236  # आपकी Telegram user ID यहां डालें

# Data storage files
PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"

# Initialize data files
def init_files():
    if not os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({"payment_method": None, "payment_photo": None}, f)

# Data loading functions
def load_products():
    try:
        with open(PRODUCTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_products(products):
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(products, f, indent=2)

def load_orders():
    try:
        with open(ORDERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_orders(orders):
    with open(ORDERS_FILE, 'w') as f:
        json.dump(orders, f, indent=2)

def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"payment_method": None, "payment_photo": None}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

# User state management
user_states = {}

# Helper functions
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_user_banned(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get('banned', False)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ U ARE BAN FROM THIS BOT")
        return
    
    if is_admin(user_id):
        keyboard = [
            ["🛍️ Shop", "👑 Admin Panel"],
            ["📦 My Orders", "ℹ️ About"]
        ]
    else:
        keyboard = [
            ["🛍️ Shop", "📦 My Orders"],
            ["ℹ️ About"]
        ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🙏 नमस्ते {update.effective_user.first_name}!\n\n"
        "IM YOUR ASSISTANT WHAT U WANT?",
        reply_markup=reply_markup
    )

# Shop catalog
async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    products = load_products()
    
    if not products:
        await update.message.reply_text("😔 PRODUCT NOT AVAILABLE RIGHT NOW")
        return
    
    products_list = list(products.items())
    items_per_page = 5
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_products = products_list[start_idx:end_idx]
    
    if not page_products:
        await update.message.reply_text("😔 PRODUCT NOT AVAILABLE RIGHT NOW")
        return
    
    keyboard = []
    
    for product_id, product in page_products:
        keyboard.append([InlineKeyboardButton(
            f"{product['name']} - ₹{product['price']}", 
            callback_data=f"product_{product_id}"
        )])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"catalog_page_{page-1}"))
    if end_idx < len(products_list):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"catalog_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🛍️ **उपलब्ध Products:**\n\n"
    text += f"Page {page + 1} of {(len(products_list) - 1) // items_per_page + 1}"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Product details
async def show_product_details(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    products = load_products()
    product = products.get(product_id)
    
    if not product:
        await update.callback_query.answer("Product नहीं मिला!")
        return
    
    text = f"📦 **{product['name']}**\n\n"
    text += f"💰 Price: ₹{product['price']}\n"
    text += f"📝 Description: {product['description']}\n"
    
    keyboard = [
        [InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_{product_id}")],
        [InlineKeyboardButton("⬅️ Back to Catalog", callback_data="back_to_catalog")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if product.get('image'):
        try:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Purchase flow
async def initiate_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    products = load_products()
    product = products.get(product_id)
    
    if not product:
        await update.callback_query.answer("Product नहीं मिला!")
        return
    
    user_states[update.effective_user.id] = {
        'action': 'buying',
        'product_id': product_id,
        'step': 'quantity'
    }
    
    keyboard = [
        [InlineKeyboardButton("1", callback_data=f"qty_1_{product_id}")],
        [InlineKeyboardButton("2", callback_data=f"qty_2_{product_id}")],
        [InlineKeyboardButton("3", callback_data=f"qty_3_{product_id}")],
        [InlineKeyboardButton("Other", callback_data=f"qty_other_{product_id}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"product_{product_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"📦 **{product['name']}**\n"
    text += f"💰 Price: ₹{product['price']} each\n\n"
    text += "🔢 QUANTITY?"
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Process quantity selection
async def process_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE, quantity, product_id):
    products = load_products()
    product = products.get(product_id)
    
    if not product:
        await update.callback_query.answer("Product नहीं मिला!")
        return
    
    total_price = int(product['price']) * int(quantity)
    
    user_states[update.effective_user.id].update({
        'quantity': quantity,
        'total_price': total_price,
        'step': 'payment'
    })
    
    settings = load_settings()
    
    if not settings.get('payment_method'):
        await update.callback_query.edit_message_text(
            "😔 Payment method अभी available नहीं है। Admin से contact करें।"
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("💳 Proceed to Payment", callback_data=f"pay_{product_id}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"product_{product_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"📦 **Order Summary:**\n\n"
    text += f"Product: {product['name']}\n"
    text += f"Quantity: {quantity}\n"
    text += f"Price per item: ₹{product['price']}\n"
    text += f"**Total: ₹{total_price}**\n\n"
    text += "Proceed to payment?"
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Show payment method
async def show_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_settings()
    user_id = update.effective_user.id
    user_state = user_states.get(user_id, {})
    
    if not user_state or user_state.get('step') != 'payment':
        await update.callback_query.answer("Invalid request!")
        return
    
    text = f"💳 **Payment Information:**\n\n"
    text += f"Total Amount: ₹{user_state['total_price']}\n\n"
    
    if settings.get('payment_method'):
        text += f"Payment Method: {settings['payment_method']}\n\n"
    
    text += "📸 Payment complete करने के बाद screenshot भेजें।"
    
    # Create order
    orders = load_orders()
    order_id = f"ORD_{len(orders) + 1}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    order_data = {
        'user_id': user_id,
        'user_name': update.effective_user.first_name,
        'username': update.effective_user.username or "N/A",
        'product_id': user_state['product_id'],
        'quantity': user_state['quantity'],
        'total_price': user_state['total_price'],
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'order_id': order_id
    }
    
    orders[order_id] = order_data
    save_orders(orders)
    
    user_states[user_id].update({
        'order_id': order_id,
        'step': 'payment_proof'
    })
    
    keyboard = [[InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send payment photo if available
    if settings.get('payment_photo'):
        try:
            await update.callback_query.message.reply_photo(
                photo=settings['payment_photo'],
                caption=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Admin Panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ आप admin नहीं हैं!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add_product")],
        [InlineKeyboardButton("❌ Delete Product", callback_data="admin_delete_product")],
        [InlineKeyboardButton("📊 Total Orders", callback_data="admin_total_orders")],
        [InlineKeyboardButton("⏳ Pending Orders", callback_data="admin_pending_orders")],
        [InlineKeyboardButton("✅ Complete Order", callback_data="admin_complete_order")],
        [InlineKeyboardButton("👥 Manage Users", callback_data="admin_manage_users")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 **Admin Panel**\n\nSelect an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Orders management
async def show_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = load_orders()
    pending_orders = {k: v for k, v in orders.items() if v['status'] == 'pending'}
    
    if not pending_orders:
        await update.callback_query.edit_message_text("😊 कोई pending orders नहीं हैं!")
        return
    
    text = "⏳ **Pending Orders:**\n\n"
    keyboard = []
    
    for order_id, order in pending_orders.items():
        products = load_products()
        product = products.get(order['product_id'], {})
        
        text += f"🆔 {order_id}\n"
        text += f"👤 User: {order['user_name']} (@{order['username']})\n"
        text += f"📦 Product: {product.get('name', 'Unknown')}\n"
        text += f"🔢 Qty: {order['quantity']}\n"
        text += f"💰 Total: ₹{order['total_price']}\n"
        text += f"📅 Date: {order['created_at'][:10]}\n\n"
        
        keyboard.append([InlineKeyboardButton(
            f"✅ Complete {order_id}", 
            callback_data=f"complete_order_{order_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_total_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = load_orders()
    
    if not orders:
        await update.callback_query.edit_message_text("😔 कोई orders नहीं हैं!")
        return
    
    total_orders = len(orders)
    pending_count = len([o for o in orders.values() if o['status'] == 'pending'])
    completed_count = len([o for o in orders.values() if o['status'] == 'completed'])
    total_revenue = sum([int(o['total_price']) for o in orders.values() if o['status'] == 'completed'])
    
    text = f"📊 **Orders Statistics:**\n\n"
    text += f"📦 Total Orders: {total_orders}\n"
    text += f"⏳ Pending: {pending_count}\n"
    text += f"✅ Completed: {completed_count}\n"
    text += f"💰 Total Revenue: ₹{total_revenue}\n\n"
    
    # Show recent orders
    recent_orders = list(orders.items())[-5:]
    if recent_orders:
        text += "🕒 **Recent Orders:**\n\n"
        for order_id, order in recent_orders:
            products = load_products()
            product = products.get(order['product_id'], {})
            status_emoji = "✅" if order['status'] == 'completed' else "⏳"
            text += f"{status_emoji} {order['user_name']} - {product.get('name', 'Unknown')} - ₹{order['total_price']}\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# Message handlers
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ U ARE BAN FROM THIS BOT")
        return
    
    if text == "🛍️ Shop":
        await show_catalog(update, context)
    elif text == "👑 Admin Panel":
        await admin_panel(update, context)
    elif text == "📦 My Orders":
        await show_my_orders(update, context)
    elif text == "ℹ️ About":
        await update.message.reply_text(
            "🏪 **About Our Shop**\n\n"
            "यह एक Telegram-based shop है जहाँ आप आसानी से products browse कर सकते हैं "
            "और order कर सकते हैं।\n\n"
            "💳 Payment के लिए UPI का इस्तेमाल करें।\n"
            "📞 Support के लिए admin से contact करें।",
            parse_mode='Markdown'
        )
    
    # Handle admin states
    user_state = user_states.get(user_id, {})
    
    if user_state.get('action') == 'add_product':
        await handle_add_product_flow(update, context, user_state)
    elif user_state.get('action') == 'payment_setup':
        await handle_payment_setup(update, context, user_state)
    elif user_state.get('action') == 'user_management':
        await handle_user_management(update, context, user_state)
    elif user_state.get('step') == 'payment_proof':
        await handle_payment_proof(update, context)

# Handle payment proof
async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state = user_states.get(user_id, {})
    
    if not user_state or user_state.get('step') != 'payment_proof':
        return
    
    order_id = user_state.get('order_id')
    if not order_id:
        return
    
    # Notify admin about payment
    orders = load_orders()
    order = orders.get(order_id)
    
    if order:
        products = load_products()
        product = products.get(order['product_id'], {})
        
        admin_message = f"💳 **New Payment Received!**\n\n"
        admin_message += f"🆔 Order ID: {order_id}\n"
        admin_message += f"👤 User: {order['user_name']} (@{order.get('username', 'N/A')})\n"
        admin_message += f"🆔 User ID: {order['user_id']}\n"
        admin_message += f"📦 Product: {product.get('name', 'Unknown')}\n"
        admin_message += f"🔢 Quantity: {order['quantity']}\n"
        admin_message += f"💰 Total Amount: ₹{order['total_price']}\n"
        admin_message += f"📅 Date: {order['created_at'][:16]}\n\n"
        admin_message += "Payment screenshot received from user."
        
        try:
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=update.message.photo[-1].file_id,
                    caption=admin_message,
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                )
        except Exception as e:
            print(f"Error sending to admin: {e}")
    
    await update.message.reply_text(
        "✅ Payment screenshot received!\n\n"
        "आपका order admin के पास भेज दिया गया है। "
        "Confirmation के लिए wait करें।"
    )
    
    # Clear user state
    user_states.pop(user_id, None)

# Callback query handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("catalog_page_"):
        page = int(data.split("_")[-1])
        await show_catalog(update, context, page)
    
    elif data.startswith("product_"):
        product_id = data.split("_")[1]
        await show_product_details(update, context, product_id)
    
    elif data.startswith("buy_"):
        product_id = data.split("_")[1]
        await initiate_purchase(update, context, product_id)
    
    elif data.startswith("qty_"):
        parts = data.split("_")
        quantity = parts[1]
        product_id = parts[2]
        
        if quantity == "other":
            await query.edit_message_text("🔢 Please type the quantity you want:")
            user_states[user_id] = {
                'action': 'buying',
                'product_id': product_id,
                'step': 'custom_quantity'
            }
        else:
            await process_quantity(update, context, quantity, product_id)
    
    elif data.startswith("pay_"):
        await show_payment_method(update, context)
    
    elif data == "back_to_catalog":
        await show_catalog(update, context)
    
    # Admin callbacks
    elif data == "admin_add_product":
        await start_add_product(update, context)
    
    elif data == "admin_pending_orders":
        await show_pending_orders(update, context)
    
    elif data == "admin_total_orders":
        await show_total_orders(update, context)
    
    elif data.startswith("complete_order_"):
        order_id = data.replace("complete_order_", "")
        await complete_order(update, context, order_id)
    
    elif data == "admin_settings":
        await show_admin_settings(update, context)
    
    elif data == "admin_manage_users":
        await show_user_management(update, 