import json
import os
import logging
from html import escape
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)

# Setup
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# File paths
LANG_FILE = "user_lang.json"
STATS_FILE = "bot_stats.json"
REQUESTS_FILE = "service_requests.json"

# Conversation states
WAITING_FOR_REQUEST = 1

# Load data
def load_json(filename, default=None):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_languages = load_json(LANG_FILE)
bot_stats = load_json(STATS_FILE, {
    "total_users": 0,
    "total_messages": 0,
    "service_requests": 0,
    "users_by_lang": {"uz": 0, "ru": 0, "en": 0}
})
service_requests = load_json(REQUESTS_FILE, [])

# TEXTS - Using HTML parse mode to avoid Markdown issues
TEXTS = {
    # ... (your existing TEXTS dictionary remains the same) ...
}

LANG_BUTTONS = [["🇺🇿 O'zbek", "🇷🇺 Русский", "🇬🇧 English"]]

# Service buttons for inline keyboard
SERVICE_BUTTONS = {
    "uz": [
        ["🔤 Tarjima", "🔍 Mahsulot Qidirish"],
        ["🎓 O'qishga Kirish", "🏢 Kanton Yarmarkasi"],
        ["🚚 Logistika", "⬅️ Orqaga"]
    ],
    "ru": [
        ["🔤 Перевод", "🔍 Поиск Товаров"],
        ["🎓 Поступление", "🏢 Кантонская Ярмарка"],
        ["🚚 Логистика", "⬅️ Назад"]
    ],
    "en": [
        ["🔤 Translation", "🔍 Product Sourcing"],
        ["🎓 Admission Help", "🏢 Canton Fair"],
        ["🚚 Logistics", "⬅️ Back"]
    ]
}

# Helper functions
def get_user_lang(user_id):
    return user_languages.get(str(user_id), "en")

def get_menu_markup(lang):
    return ReplyKeyboardMarkup(TEXTS["menu"][lang], resize_keyboard=True)

def get_services_markup(lang):
    return ReplyKeyboardMarkup(SERVICE_BUTTONS[lang], resize_keyboard=True)

def update_stats(stat_type, increment=1):
    bot_stats[stat_type] = bot_stats.get(stat_type, 0) + increment
    save_json(STATS_FILE, bot_stats)

def is_admin(user_id):
    return user_id in ADMIN_IDS

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in user_languages:
        update_stats("total_users")
    keyboard = ReplyKeyboardMarkup(LANG_BUTTONS, resize_keyboard=True)
    await update.message.reply_text(TEXTS["start"]["en"], reply_markup=keyboard, parse_mode="HTML")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text("📋 Main menu", reply_markup=get_menu_markup(lang), parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS["help"][lang], parse_mode="HTML")

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS["contact"][lang], parse_mode="HTML")

async def pricing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS["pricing"][lang], parse_mode="HTML")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS["about"][lang], parse_mode="HTML")

# Services handling
async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(
        TEXTS["services_intro"][lang], 
        reply_markup=get_services_markup(lang), 
        parse_mode="HTML"
    )

async def handle_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    text = update.message.text
    
    service_mapping = {
        "uz": {
            "🔤 Tarjima": "translation",
            "🔍 Mahsulot Qidirish": "sourcing", 
            "🎓 O'qishga Kirish": "admission",
            "🏢 Kanton Yarmarkasi": "canton",
            "🚚 Logistika": "logistics",
            "⬅️ Orqaga": "back"
        },
        "ru": {
            "🔤 Перевод": "translation",
            "🔍 Поиск Товаров": "sourcing",
            "🎓 Поступление": "admission", 
            "🏢 Кантонская Ярмарка": "canton",
            "🚚 Логистика": "logistics",
            "⬅️ Назад": "back"
        },
        "en": {
            "🔤 Translation": "translation",
            "🔍 Product Sourcing": "sourcing",
            "🎓 Admission Help": "admission",
            "🏢 Canton Fair": "canton", 
            "🚚 Logistics": "logistics",
            "⬅️ Back": "back"
        }
    }
    
    service_key = service_mapping[lang].get(text)
    
    if service_key == "back":
        await update.message.reply_text("📋 Main menu", reply_markup=get_menu_markup(lang))
    elif service_key in TEXTS["service_details"]:
        await update.message.reply_text(
            TEXTS["service_details"][service_key][lang],
            parse_mode="HTML",
            reply_markup=get_services_markup(lang)
        )
    else:
        await update.message.reply_text(
            "❌ Service not found. Please try again.",
            reply_markup=get_menu_markup(lang)
        )

# Request conversation
async def request_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS["request_prompt"][lang], parse_mode="HTML")
    return WAITING_FOR_REQUEST

async def request_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    request = {
        "user_id": user_id,
        "username": update.effective_user.username or "N/A",
        "first_name": update.effective_user.first_name or "",
        "last_name": update.effective_user.last_name or "",
        "message": update.message.text,
        "timestamp": datetime.now().isoformat(),
        "language": lang
    }
    service_requests.append(request)
    save_json(REQUESTS_FILE, service_requests)
    update_stats("service_requests")

    # Notify admins
    admin_msg = f"📝 <b>New Service Request</b>\n👤 User: {request['first_name']}\nID: {user_id}\n📱 @{request['username']}\nMessage:\n{escape(update.message.text)}"
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    await update.message.reply_text(TEXTS["request_received"][lang], reply_markup=get_menu_markup(lang), parse_mode="HTML")
    return ConversationHandler.END

async def request_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text("❌ Cancelled", reply_markup=get_menu_markup(lang))
    return ConversationHandler.END

# Handle messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    lang = get_user_lang(user_id)
    update_stats("total_messages")

    # Language selection
    if text in ["🇬🇧 English", "🇷🇺 Русский", "🇺🇿 O'zbek"]:
        old_lang = user_languages.get(user_id)
        new_lang = {"🇬🇧 English": "en", "🇷🇺 Русский": "ru", "🇺🇿 O'zbek": "uz"}[text]
        user_languages[user_id] = new_lang
        if old_lang != new_lang:
            if old_lang:
                bot_stats.setdefault("users_by_lang", {})[old_lang] -= 1
            bot_stats.setdefault("users_by_lang", {})[new_lang] = bot_stats.get("users_by_lang", {}).get(new_lang, 0) + 1
        save_json(LANG_FILE, user_languages)
        save_json(STATS_FILE, bot_stats)
        await update.message.reply_text(TEXTS["lang_changed"][new_lang], reply_markup=get_menu_markup(new_lang))
        return
    
    # Menu options handling
    menu_options = {
        "uz": ["🛠 Xizmatlar", "📞 Aloqa", "💼 Narxlar", "📝 So'rov yuborish", "🌏 Til", "ℹ️ Haqida", "❓ Yordam"],
        "ru": ["🛠 Услуги", "📞 Контакт", "💼 Цены", "📝 Отправить запрос", "🌏 Язык", "ℹ️ О боте", "❓ Помощь"],
        "en": ["🛠 Services", "📞 Contact", "💼 Pricing", "📝 Send Request", "🌏 Language", "ℹ️ About", "❓ Help"]
    }
    
    if text in menu_options[lang]:
        if text in ["🛠 Xizmatlar", "🛠 Услуги", "🛠 Services"]:
            await show_services(update, context)
        elif text in ["📞 Aloqa", "📞 Контакт", "📞 Contact"]:
            await contact_command(update, context)
        elif text in ["💼 Narxlar", "💼 Цены", "💼 Pricing"]:
            await pricing_command(update, context)
        elif text in ["ℹ️ Haqida", "ℹ️ О боте", "ℹ️ About"]:
            await about_command(update, context)
        elif text in ["❓ Yordam", "❓ Помощь", "❓ Help"]:
            await help_command(update, context)
        elif text in ["🌏 Til", "🌏 Язык", "🌏 Language"]:
            keyboard = ReplyKeyboardMarkup(LANG_BUTTONS, resize_keyboard=True)
            await update.message.reply_text("🌏 Choose language:", reply_markup=keyboard)
    else:
        # Check if it's a service selection
        service_texts = []
        for lang_services in SERVICE_BUTTONS.values():
            for row in lang_services:
                service_texts.extend(row)
        
        if text in service_texts:
            await handle_service_selection(update, context)
        else:
            # Default response for unknown messages
            await update.message.reply_text(
                "❓ I don't understand that command. Please use the menu buttons.",
                reply_markup=get_menu_markup(lang)
            )

# Main function
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in environment variables!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Improved conversation handler with better regex
    request_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^(📝 Send Request|📝 Отправить запрос|📝 So'rov yuborish)$"), 
                request_start
            )
        ],
        states={
            WAITING_FOR_REQUEST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, request_receive)
            ]
        },
        fallbacks=[CommandHandler("cancel", request_cancel)]
    )

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("contact", contact_command))
    app.add_handler(CommandHandler("pricing", pricing_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(request_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 China Agent Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()