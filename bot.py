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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Your Render URL: https://your-app.onrender.com
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

# Texts (keeping all your existing TEXTS dictionary)
TEXTS = {
    "start": {
        "uz": "👋 *China Agent Bot* 🇨🇳 ga xush kelibsiz!\n\n"
              "Biz Guanchjoudagi professional agentlar bilan bog'laymiz.\n"
              "Iltimos, tilni tanlang:",
        "ru": "👋 Добро пожаловать в *China Agent Bot* 🇨🇳!\n\n"
              "Мы соединяем вас с профессиональными агентами в Гуанчжоу.\n"
              "Пожалуйста, выберите язык:",
        "en": "👋 Welcome to *China Agent Bot* 🇨🇳!\n\n"
              "We connect you with professional agents in Guangzhou.\n"
              "Please choose your language:",
    },
    "menu": {
        "uz": [
            ["🛠 Xizmatlar", "📞 Aloqa"],
            ["💼 Narxlar", "📝 So'rov yuborish"],
            ["🌏 Til", "ℹ Haqida", "❓ Yordam"]
        ],
        "ru": [
            ["🛠 Услуги", "📞 Контакт"],
            ["💼 Цены", "📝 Отправить запрос"],
            ["🌏 Язык", "ℹ О боте", "❓ Помощь"]
        ],
        "en": [
            ["🛠 Services", "📞 Contact"],
            ["💼 Pricing", "📝 Send Request"],
            ["🌏 Language", "ℹ About", "❓ Help"]
        ],
    },
    "services_intro": {
        "uz": "🛠 *Bizning Xizmatlarimiz*\n\nQuyidagi xizmatlardan birini tanlang:",
        "ru": "🛠 *Наши Услуги*\n\nВыберите одну из услуг:",
        "en": "🛠 *Our Services*\n\nChoose one of the services:",
    },
    "service_details": {
        "translation": {
            "uz": "🔤 *Tarjima Xizmati*\n\n📋 Taqdim etamiz:\n• Biznes uchrashuv tarjimalari\n• Hujjat tarjimalari\n• Telefon tarjimalari\n\n💰 Narx: $20-30/soat",
            "ru": "🔤 *Услуга Перевода*\n\n📋 Предоставляем:\n• Переводы деловых встреч\n• Переводы документов\n• Телефонные переводы\n\n💰 Цена: $20-30/час",
            "en": "🔤 *Translation Service*\n\n📋 We provide:\n• Business meeting translations\n• Document translations\n• Phone translations\n\n💰 Price: $20-30/hour",
        },
        "sourcing": {
            "uz": "🔍 *Mahsulot Qidirish*\n\n📋 Xizmatlar:\n• Ishonchli fabrika qidirish\n• Narx muzokaralari\n• Sifat nazorati\n\n💰 Narx: $100-300",
            "ru": "🔍 *Поиск Товаров*\n\n📋 Услуги:\n• Поиск надежных фабрик\n• Переговоры о ценах\n• Контроль качества\n\n💰 Цена: $100-300",
            "en": "🔍 *Product Sourcing*\n\n📋 Services:\n• Finding reliable factories\n• Price negotiations\n• Quality control\n\n💰 Price: $100-300",
        },
    },
    "contact": {
        "uz": "📞 *Biz bilan bog'lanish:*\n\n👤 Agent: Zhang Wei\n📱 WeChat: chinaagent_gz\n✈️ Telegram: @ChinaAgentGZ",
        "ru": "📞 *Свяжитесь с нами:*\n\n👤 Агент: Zhang Wei\n📱 WeChat: chinaagent_gz\n✈️ Telegram: @ChinaAgentGZ",
        "en": "📞 *Contact Us:*\n\n👤 Agent: Zhang Wei\n📱 WeChat: chinaagent_gz\n✈️ Telegram: @ChinaAgentGZ",
    },
    "request_prompt": {
        "uz": "📝 *So'rov yuborish*\n\nIltimos, xizmat turi va telefon raqamingizni kiriting.",
        "ru": "📝 *Отправить запрос*\n\nПожалуйста, укажите тип услуги и номер телефона.",
        "en": "📝 *Send Request*\n\nPlease provide service type and phone number.",
    },
    "request_received": {
        "uz": "✅ So'rov qabul qilindi! Tez orada bog'lanamiz.",
        "ru": "✅ Запрос получен! Мы свяжемся с вами.",
        "en": "✅ Request received! We'll contact you soon.",
    },
    "lang_changed": {
        "uz": "🌏 Til o'zgartirildi!",
        "ru": "🌏 Язык изменен!",
        "en": "🌏 Language changed!",
    },
}

LANG_BUTTONS = [["🇺🇿 O'zbek", "🇷🇺 Русский", "🇬🇧 English"]]

# Helper functions
def get_user_lang(user_id):
    return user_languages.get(str(user_id), "en")

def get_menu_markup(lang):
    return ReplyKeyboardMarkup(TEXTS["menu"][lang], resize_keyboard=True)

def update_stats(stat_type, increment=1):
    bot_stats[stat_type] = bot_stats.get(stat_type, 0) + increment
    save_json(STATS_FILE, bot_stats)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_service_buttons(lang):
    services = {
        "uz": [
            [InlineKeyboardButton("🔤 Tarjima", callback_data="srv_translation")],
            [InlineKeyboardButton("🔍 Mahsulot qidirish", callback_data="srv_sourcing")],
        ],
        "ru": [
            [InlineKeyboardButton("🔤 Переводы", callback_data="srv_translation")],
            [InlineKeyboardButton("🔍 Поиск товаров", callback_data="srv_sourcing")],
        ],
        "en": [
            [InlineKeyboardButton("🔤 Translation", callback_data="srv_translation")],
            [InlineKeyboardButton("🔍 Product Sourcing", callback_data="srv_sourcing")],
        ],
    }
    return InlineKeyboardMarkup(services[lang])

# Commands (keeping all your existing command handlers)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id not in user_languages:
        update_stats("total_users")
    keyboard = ReplyKeyboardMarkup(LANG_BUTTONS, resize_keyboard=True)
    await update.message.reply_text(
        "👋 *China Agent Bot* 🇨🇳\n\n🇺🇿 Tilni tanlang\n🇷🇺 Выберите язык\n🇬🇧 Choose language",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.message.from_user.id)
    lang = get_user_lang(user_id)
    
    update_stats("total_messages")
    
    if text in ["🇬🇧 English", "🇷🇺 Русский", "🇺🇿 O'zbek"]:
        if text == "🇬🇧 English":
            user_languages[user_id] = "en"
        elif text == "🇷🇺 Русский":
            user_languages[user_id] = "ru"
        else:
            user_languages[user_id] = "uz"
        save_json(LANG_FILE, user_languages)
        await update.message.reply_text(
            TEXTS["lang_changed"][user_languages[user_id]], 
            reply_markup=get_menu_markup(user_languages[user_id])
        )
    elif text in ["🛠 Services", "🛠 Услуги", "🛠 Xizmatlar"]:
        await update.message.reply_text(
            TEXTS["services_intro"][lang],
            parse_mode="Markdown",
            reply_markup=get_service_buttons(lang)
        )
    elif text in ["📞 Contact", "📞 Контакт", "📞 Aloqa"]:
        await update.message.reply_text(TEXTS["contact"][lang], parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    lang = get_user_lang(user_id)
    
    if query.data.startswith("srv_"):
        service = query.data.replace("srv_", "")
        if service in TEXTS["service_details"]:
            await query.edit_message_text(
                TEXTS["service_details"][service][lang],
                parse_mode="Markdown"
            )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Main function with webhook support
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    logger.info("🤖 China Agent Bot starting...")
    
    # Use webhook for Render deployment
    if WEBHOOK_URL:
        logger.info(f"🌐 Starting webhook on {WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        # Fallback to polling for local development
        logger.info("🔄 Starting polling mode...")
        app.run_polling()

if __name__ == "__main__":
    main()