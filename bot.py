import os
import logging
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    ConversationHandler,
    CallbackContext, 
    filters
)
import datetime
import random
import string

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# SQLite database setup
DB_NAME = "telegram_bot.db"

# Conversation states
REGISTER, AUTHENTICATE, MAIN_MENU, ADMIN_MENU, BROADCAST_MESSAGE, BROADCAST_MEDIA = range(6)

# Admin credentials
ADMIN_ID = "7715257236"  # Aapki admin ID
ADMIN_PASS = "KTATZ"  # Aap apna password set karen

# Bot token
TOKEN = "8291608976:AAEeii9LVk-fIGN9nkR7_7gBNPB-fhEDmjM"  # Aapka bot token

# Database initialization
def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE,
        login_id TEXT UNIQUE,
        password TEXT,
        registered_at TEXT,
        is_active INTEGER DEFAULT 1
    )
    ''')
    
    # Create content table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        data TEXT,
        sent_by TEXT,
        sent_at TEXT
    )
    ''')
    
    # Create user_ids table for admin
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_ids (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE
    )
    ''')
    
    # Insert admin user if not exists
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (ADMIN_ID,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (user_id, login_id, password, registered_at, is_active) VALUES (?, ?, ?, ?, ?)",
            (ADMIN_ID, "admin", ADMIN_PASS, datetime.datetime.now().isoformat(), 1)
        )
    
    # Insert some initial user IDs if table is empty
    cursor.execute("SELECT COUNT(*) FROM user_ids")
    if cursor.fetchone()[0] == 0:
        for _ in range(10):
            user_id = f"user{''.join(random.choices(string.ascii_letters + string.digits, k=8))}"
            cursor.execute("INSERT INTO user_ids (user_id) VALUES (?)", (user_id,))
    
    conn.commit()
    conn.close()

# Database helper functions
def db_execute(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def db_fetchone(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchone()
    conn.close()
    return result

def db_fetchall(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchall()
    conn.close()
    return result

async def start(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    
    # Check if user is admin
    if user_id == ADMIN_ID:
        keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "🌟 Admin Panel 🌟\nPlease choose an option:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
    
    # Check if regular user exists
    user = db_fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
    
    if user:
        await update.message.reply_text(
            "Welcome back! Please enter your password to continue:",
            reply_markup=ReplyKeyboardRemove()
        )
        return AUTHENTICATE
    else:
        await update.message.reply_text(
            "Welcome! You need to register first. Please enter the ID provided by admin:",
            reply_markup=ReplyKeyboardRemove()
        )
        return REGISTER

async def register(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text
    user_id = str(update.effective_user.id)
    
    # Check if the provided ID exists in admin's list
    user_data = db_fetchone("SELECT * FROM user_ids WHERE user_id = ?", (user_input,))
    
    if user_data:
        # Store the user ID temporarily for password setup
        context.user_data["temp_id"] = user_input
        await update.message.reply_text(
            "✅ ID verified. Please set your password:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END  # We'll handle password in a separate handler
    else:
        await update.message.reply_text(
            "❌ Invalid ID. Please contact admin for a valid ID or try again:"
        )
        return REGISTER

async def set_password(update: Update, context: CallbackContext) -> None:
    password = update.message.text
    user_input_id = context.user_data.get("temp_id")
    user_id = str(update.effective_user.id)
    
    if user_input_id:
        # Save user to database
        db_execute(
            "INSERT INTO users (user_id, login_id, password, registered_at, is_active) VALUES (?, ?, ?, ?, ?)",
            (user_id, user_input_id, password, datetime.datetime.now().isoformat(), 1)
        )
        
        # Remove the ID from admin's available IDs
        db_execute("DELETE FROM user_ids WHERE user_id = ?", (user_input_id,))
        
        await update.message.reply_text(
            "✅ Registration successful! You can now use /login to access the bot.",
            reply_markup=ReplyKeyboardRemove()
        )
        del context.user_data["temp_id"]
    else:
        await update.message.reply_text(
            "❌ Something went wrong. Please start again with /start."
        )

async def login(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    
    # Check if user is admin
    if user_id == ADMIN_ID:
        keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "🌟 Admin Panel 🌟\nPlease choose an option:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
    
    # Check if regular user exists
    user = db_fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
    
    if user:
        await update.message.reply_text(
            "Please enter your password:",
            reply_markup=ReplyKeyboardRemove()
        )
        return AUTHENTICATE
    else:
        await update.message.reply_text(
            "You need to register first. Please use /start to begin registration."
        )
        return ConversationHandler.END

async def authenticate(update: Update, context: CallbackContext) -> int:
    password = update.message.text
    user_id = str(update.effective_user.id)
    
    user = db_fetchone("SELECT * FROM users WHERE user_id = ? AND password = ?", (user_id, password))
    
    if user:
        keyboard = [["📺 View Content", "ℹ️ My Account"], ["🚪 Logout"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "✅ Authentication successful! Choose an option:",
            reply_markup=reply_markup
        )
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "❌ Incorrect password. Please try again:"
        )
        return AUTHENTICATE

async def main_menu(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text
    user_id = str(update.effective_user.id)
    
    if user_input == "📺 View Content":
        # Get all content from database
        contents = db_fetchall("SELECT * FROM content ORDER BY sent_at DESC LIMIT 10")
        
        if contents:
            sent_count = 0
            for content in contents:
                if sent_count >= 10:  # Limit to 10 recent items
                    break
                    
                try:
                    content_id, content_type, content_data, sent_by, sent_at = content
                    if content_type == 'text':
                        await update.message.reply_text(content_data)
                    elif content_type == 'photo':
                        await update.message.reply_photo(content_data)
                    elif content_type == 'video':
                        await update.message.reply_video(content_data)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending content: {e}")
                    
            if sent_count == 0:
                await update.message.reply_text("No content available yet.")
        else:
            await update.message.reply_text("No content available yet.")
            
        keyboard = [["📺 View Content", "ℹ️ My Account"], ["🚪 Logout"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Choose an option:",
            reply_markup=reply_markup
        )
        return MAIN_MENU
        
    elif user_input == "ℹ️ My Account":
        user = db_fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_id, login_id, password, registered_at, is_active = user
        reg_date = datetime.datetime.fromisoformat(registered_at).strftime('%Y-%m-%d %H:%M')
        
        await update.message.reply_text(
            f"📋 Your account info:\n\n🆔 ID: {login_id}\n📅 Registered: {reg_date}"
        )
        
        keyboard = [["📺 View Content", "ℹ️ My Account"], ["🚪 Logout"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Choose an option:",
            reply_markup=reply_markup
        )
        return MAIN_MENU
        
    elif user_input == "🚪 Logout":
        await update.message.reply_text(
            "Logged out successfully.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def admin_menu(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text
    user_id = str(update.effective_user.id)
    
    if user_input == "📢 Broadcast Message":
        keyboard = [["📝 Text Message", "🖼️ Photo"], ["🎥 Video", "↩️ Back"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Select broadcast type:",
            reply_markup=reply_markup
        )
        return BROADCAST_MESSAGE
        
    elif user_input == "👥 Total Users":
        total_users = db_fetchone("SELECT COUNT(*) FROM users")[0]
        await update.message.reply_text(f"📊 Total registered users: {total_users}")
        
        keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
        
    elif user_input == "🆔 Generate User IDs":
        # Generate 5 new user IDs
        new_ids = [f"user{''.join(random.choices(string.ascii_letters + string.digits, k=8))}" for _ in range(5)]
        
        # Store them in database
        for new_id in new_ids:
            db_execute("INSERT INTO user_ids (user_id) VALUES (?)", (new_id,))
        
        id_list = "🆔 New User IDs generated:\n\n" + "\n".join(new_ids)
        await update.message.reply_text(id_list)
        
        keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
        
    elif user_input == "📊 Statistics":
        total_users = db_fetchone("SELECT COUNT(*) FROM users")[0]
        active_users = db_fetchone("SELECT COUNT(*) FROM users WHERE is_active = 1")[0]
        total_content = db_fetchone("SELECT COUNT(*) FROM content")[0]
        
        stats_text = f"""
        📊 Bot Statistics:
        
        👥 Total Users: {total_users}
        ✅ Active Users: {active_users}
        📨 Total Content: {total_content}
        """
        
        await update.message.reply_text(stats_text)
        
        keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
        
    elif user_input == "↩️ Back":
        keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU

async def broadcast_message(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text
    user_id = str(update.effective_user.id)
    
    if user_input == "📝 Text Message":
        await update.message.reply_text(
            "Please send the text message you want to broadcast:",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["broadcast_type"] = "text"
        return BROADCAST_MEDIA
        
    elif user_input == "🖼️ Photo":
        await update.message.reply_text(
            "Please send the photo you want to broadcast:",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["broadcast_type"] = "photo"
        return BROADCAST_MEDIA
        
    elif user_input == "🎥 Video":
        await update.message.reply_text(
            "Please send the video you want to broadcast:",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["broadcast_type"] = "video"
        return BROADCAST_MEDIA
        
    elif user_input == "↩️ Back":
        keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU

async def broadcast_media(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    broadcast_type = context.user_data.get("broadcast_type")
    
    # Check if message is text, photo, or video
    if broadcast_type == "text" and update.message.text:
        content_type = "text"
        content_data = update.message.text
    elif broadcast_type == "photo" and update.message.photo:
        content_type = "photo"
        content_data = update.message.photo[-1].file_id  # Get the highest resolution photo
    elif broadcast_type == "video" and update.message.video:
        content_type = "video"
        content_data = update.message.video.file_id
    else:
        await update.message.reply_text("❌ Unsupported message type or format.")
        keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
    
    # Save content to database
    db_execute(
        "INSERT INTO content (type, data, sent_by, sent_at) VALUES (?, ?, ?, ?)",
        (content_type, content_data, user_id, datetime.datetime.now().isoformat())
    )
    
    # Get all users
    users = db_fetchall("SELECT user_id FROM users WHERE is_active = 1 AND user_id != ?", (ADMIN_ID,))
    user_count = len(users)
    
    # Send to all users
    success_count = 0
    for user in users:
        try:
            if content_type == "text":
                await context.bot.send_message(chat_id=user[0], text=content_data)
            elif content_type == "photo":
                await context.bot.send_photo(chat_id=user[0], photo=content_data)
            elif content_type == "video":
                await context.bot.send_video(chat_id=user[0], video=content_data)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send message to user {user[0]}: {e}")
    
    await update.message.reply_text(f"✅ Message broadcasted to {success_count}/{user_count} users!")
    
    keyboard = [["📢 Broadcast Message", "👥 Total Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Admin panel:",
        reply_markup=reply_markup
    )
    return ADMIN_MENU

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "Operation cancelled.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main() -> None:
    # Initialize database
    init_database()
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Add conversation handler with the states
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("login", login)],
        states={
            REGISTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, register)],
            AUTHENTICATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, authenticate)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu)],
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)],
            BROADCAST_MEDIA: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_media)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handler for password setting (after registration)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_password), group=1)
    
    # Add conversation handler
    application.add_handler(conv_handler)

    # Start the Bot
    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
