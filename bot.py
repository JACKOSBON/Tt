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
REGISTER, AUTHENTICATE, MAIN_MENU, ADMIN_MENU, BROADCAST_MESSAGE, BROADCAST_MEDIA, MANAGE_USERS = range(7)

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
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        registered_at TEXT,
        is_active INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0
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
            "INSERT INTO users (user_id, login_id, password, username, first_name, is_active, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ADMIN_ID, "admin", ADMIN_PASS, "Admin", "Admin", 1, 1)
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
    username = update.effective_user.username or "N/A"
    first_name = update.effective_user.first_name or "N/A"
    last_name = update.effective_user.last_name or "N/A"
    
    # Check if user is admin
    if user_id == ADMIN_ID:
        keyboard = [["📢 Broadcast Message", "👥 Manage Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "🌟 Admin Panel 🌟\nPlease choose an option:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
    
    # Check if user is banned
    banned_user = db_fetchone("SELECT * FROM users WHERE user_id = ? AND is_banned = 1", (user_id,))
    if banned_user:
        await update.message.reply_text(
            "❌ Your account has been banned. Please contact admin for more information.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Check if regular user exists
    user = db_fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
    
    if user:
        # Check if user is verified
        if user[9] == 0:  # is_verified field
            await update.message.reply_text(
                "⏳ Your account is pending verification. Please wait for admin approval.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        else:
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
    username = update.effective_user.username or "N/A"
    first_name = update.effective_user.first_name or "N/A"
    last_name = update.effective_user.last_name or "N/A"
    
    # Check if the provided ID exists in admin's list
    user_data = db_fetchone("SELECT * FROM user_ids WHERE user_id = ?", (user_input,))
    
    if user_data:
        # Store the user ID temporarily for password setup
        context.user_data["temp_id"] = user_input
        context.user_data["username"] = username
        context.user_data["first_name"] = first_name
        context.user_data["last_name"] = last_name
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
    username = context.user_data.get("username")
    first_name = context.user_data.get("first_name")
    last_name = context.user_data.get("last_name")
    
    if user_input_id:
        # Save user to database (not verified yet)
        db_execute(
            "INSERT INTO users (user_id, login_id, password, username, first_name, last_name, registered_at, is_active, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, user_input_id, password, username, first_name, last_name, datetime.datetime.now().isoformat(), 0, 0)
        )
        
        # Remove the ID from admin's available IDs
        db_execute("DELETE FROM user_ids WHERE user_id = ?", (user_input_id,))
        
        # Send notification to admin
        try:
            user_info = f"🆕 New User Registration:\n\n👤 User: {first_name} {last_name}\n🔖 Username: @{username}\n🆔 User ID: {user_id}\n📝 Login ID: {user_input_id}"
            
            keyboard = [[f"verify_{user_id}", f"ban_{user_id}"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=user_info,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending notification to admin: {e}")
        
        await update.message.reply_text(
            "✅ Registration successful! Your account is pending verification by admin. You will be notified once approved.",
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
        keyboard = [["📢 Broadcast Message", "👥 Manage Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "🌟 Admin Panel 🌟\nPlease choose an option:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
    
    # Check if user is banned
    banned_user = db_fetchone("SELECT * FROM users WHERE user_id = ? AND is_banned = 1", (user_id,))
    if banned_user:
        await update.message.reply_text(
            "❌ Your account has been banned. Please contact admin for more information.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Check if regular user exists and is verified
    user = db_fetchone("SELECT * FROM users WHERE user_id = ? AND is_verified = 1", (user_id,))
    
    if user:
        await update.message.reply_text(
            "Please enter your password:",
            reply_markup=ReplyKeyboardRemove()
        )
        return AUTHENTICATE
    else:
        user_exists = db_fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if user_exists:
            await update.message.reply_text(
                "⏳ Your account is pending verification. Please wait for admin approval."
            )
        else:
            await update.message.reply_text(
                "You need to register first. Please use /start to begin registration."
            )
        return ConversationHandler.END

async def authenticate(update: Update, context: CallbackContext) -> int:
    password = update.message.text
    user_id = str(update.effective_user.id)
    
    user = db_fetchone("SELECT * FROM users WHERE user_id = ? AND password = ? AND is_verified = 1", (user_id, password))
    
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
            "❌ Incorrect password or account not verified. Please try again:"
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
        user_id_db, login_id, password, username, first_name, last_name, registered_at, is_active, is_verified, is_banned = user
        reg_date = datetime.datetime.fromisoformat(registered_at).strftime('%Y-%m-%d %H:%M')
        
        status = "✅ Verified" if is_verified else "⏳ Pending Verification"
        if is_banned:
            status = "❌ Banned"
            
        await update.message.reply_text(
            f"📋 Your account info:\n\n🆔 ID: {login_id}\n👤 Name: {first_name} {last_name}\n🔖 Username: @{username}\n📅 Registered: {reg_date}\n📊 Status: {status}"
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
        
    elif user_input == "👥 Manage Users":
        # Get pending users
        pending_users = db_fetchall("SELECT user_id, login_id, username, first_name, last_name FROM users WHERE is_verified = 0 AND is_banned = 0")
        
        if pending_users:
            users_text = "⏳ Pending Users:\n\n"
            keyboard = []
            
            for user in pending_users:
                user_id_db, login_id, username, first_name, last_name = user
                users_text += f"👤 {first_name} {last_name} (@{username}) - ID: {login_id}\n"
                keyboard.append([f"verify_{user_id_db}", f"ban_{user_id_db}"])
            
            keyboard.append(["↩️ Back"])
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(users_text, reply_markup=reply_markup)
            return MANAGE_USERS
        else:
            total_users = db_fetchone("SELECT COUNT(*) FROM users WHERE is_verified = 1")[0]
            banned_users = db_fetchone("SELECT COUNT(*) FROM users WHERE is_banned = 1")[0]
            
            users_text = f"📊 Users Statistics:\n\n✅ Verified Users: {total_users}\n⏳ Pending Users: 0\n❌ Banned Users: {banned_users}"
            
            keyboard = [["📢 Broadcast Message", "👥 Manage Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(users_text, reply_markup=reply_markup)
            return ADMIN_MENU
        
    elif user_input == "🆔 Generate User IDs":
        # Generate 5 new user IDs
        new_ids = [f"user{''.join(random.choices(string.ascii_letters + string.digits, k=8))}" for _ in range(5)]
        
        # Store them in database
        for new_id in new_ids:
            db_execute("INSERT INTO user_ids (user_id) VALUES (?)", (new_id,))
        
        id_list = "🆔 New User IDs generated:\n\n" + "\n".join(new_ids)
        await update.message.reply_text(id_list)
        
        keyboard = [["📢 Broadcast Message", "👥 Manage Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
        
    elif user_input == "📊 Statistics":
        total_users = db_fetchone("SELECT COUNT(*) FROM users WHERE is_verified = 1")[0]
        pending_users = db_fetchone("SELECT COUNT(*) FROM users WHERE is_verified = 0 AND is_banned = 0")[0]
        banned_users = db_fetchone("SELECT COUNT(*) FROM users WHERE is_banned = 1")[0]
        total_content = db_fetchone("SELECT COUNT(*) FROM content")[0]
        
        stats_text = f"""
        📊 Bot Statistics:
        
        ✅ Verified Users: {total_users}
        ⏳ Pending Users: {pending_users}
        ❌ Banned Users: {banned_users}
        📨 Total Content: {total_content}
        """
        
        await update.message.reply_text(stats_text)
        
        keyboard = [["📢 Broadcast Message", "👥 Manage Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU
        
    elif user_input == "↩️ Back":
        keyboard = [["📢 Broadcast Message", "👥 Manage Users"], ["🆔 Generate User IDs", "📊 Statistics"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Admin panel:",
            reply_markup=reply_markup
        )
        return ADMIN_MENU

async def manage_users(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text
    user_id = str(update.effective_user.id)
    
    if user_input.startswith("verify_"):
        user_to_verify = user_input.split("_")[1]
        
        # Verify the user
        db_execute("UPDATE users SET is_verified = 1, is_active = 1 WHERE user_id = ?", (user_to_verify,))
        
        # Notify the user
        try:
            user_info = db_fetchone("SELECT first_name, login_id FROM users WHERE user_id = ?", (user_to_verify,))
            if user_info:
                first_name, login_id = user_info
                await context.bot.send_message(
                    chat_id=user_to_verify,
                    text=f"✅ Your account has been verified! You can now use /login to access the bot."
                )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")
        
        await update.message.reply_text(f"✅ User {user_to_verify} has been verified.")
        
        # Return to manage users
        return await admin_menu(update, context)
        
    elif user_input.startswith("ban_"):
        user_to_ban = user_input.split("_")[1]
        
        # Ban the user
        db_execute("UPDATE users SET is_banned = 1, is_active = 0, is_verified = 0 WHERE user_id = ?", (user_to_ban,))
        
        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=user_to_ban,
                text="❌ Your account has been banned by admin. Please contact admin for more information."
            )
        except Exce
