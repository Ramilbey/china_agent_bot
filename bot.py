import json
import os
import logging
import asyncio
import httpx
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

# TEXTS dictionary - COMPLETE VERSION
TEXTS = {
    "start": {
        "en": "👋 <b>Welcome to China Agent Bot!</b>\n\n🇨🇳 Your reliable partner for business in China\n\nPlease select your language:",
        "ru": "👋 <b>Добро пожаловать в China Agent Bot!</b>\n\n🇨🇳 Ваш надежный партнер для бизнеса в Китае\n\nПожалуйста, выберите язык:",
        "uz": "👋 <b>China Agent Botga xush kelibsiz!</b>\n\n🇨🇳 Xitoydagi biznesingiz uchun ishonchli hamkor\n\nIltimos, tilni tanlang:"
    },
    "lang_changed": {
        "en": "✅ Language changed to English\n\nUse the menu below to navigate:",
        "ru": "✅ Язык изменен на русский\n\nИспользуйте меню ниже для навигации:",
        "uz": "✅ Til o'zbek tiliga o'zgartirildi\n\nQuyidagi menyudan foydalaning:"
    },
    "menu": {
        "en": [["🛠 Services", "📞 Contact"], ["💼 Pricing", "📝 Send Request"], ["🌏 Language", "ℹ️ About", "❓ Help"]],
        "ru": [["🛠 Услуги", "📞 Контакт"], ["💼 Цены", "📝 Отправить запрос"], ["🌏 Язык", "ℹ️ О боте", "❓ Помощь"]],
        "uz": [["🛠 Xizmatlar", "📞 Aloqa"], ["💼 Narxlar", "📝 So'rov yuborish"], ["🌏 Til", "ℹ️ Haqida", "❓ Yordam"]]
    },
    "services_intro": {
        "en": "🛠 <b>Our Services:</b>\n\nSelect a service to learn more:",
        "ru": "🛠 <b>Наши Услуги:</b>\n\nВыберите услугу для подробностей:",
        "uz": "🛠 <b>Bizning Xizmatlar:</b>\n\nBatafsil ma'lumot olish uchun xizmatni tanlang:"
    },
    "service_details": {
        "translation": {
            "en": "🔤 <b>Translation Services</b>\n\n✅ Documents\n✅ Contracts\n✅ Business meetings\n✅ Live interpretation\n\n📞 Contact us for pricing",
            "ru": "🔤 <b>Услуги Перевода</b>\n\n✅ Документы\n✅ Контракты\n✅ Деловые встречи\n✅ Синхронный перевод\n\n📞 Свяжитесь для уточнения цен",
            "uz": "🔤 <b>Tarjima Xizmatlari</b>\n\n✅ Hujjatlar\n✅ Shartnomalar\n✅ Biznes uchrashuvlar\n✅ Jonli tarjima\n\n📞 Narxlar uchun bog'laning"
        },
        "sourcing": {
            "en": "🔍 <b>Product Sourcing</b>\n\n✅ Find manufacturers\n✅ Quality control\n✅ Price negotiation\n✅ Sample ordering\n\n📞 Let's find your perfect supplier!",
            "ru": "🔍 <b>Поиск Товаров</b>\n\n✅ Поиск производителей\n✅ Контроль качества\n✅ Переговоры о цене\n✅ Заказ образцов\n\n📞 Найдем идеального поставщика!",
            "uz": "🔍 <b>Mahsulot Qidirish</b>\n\n✅ Ishlab chiqaruvchi topish\n✅ Sifat nazorati\n✅ Narx muzokara\n✅ Namuna buyurtma\n\n📞 Eng yaxshi yetkazib beruvchini topamiz!"
        },
        "admission": {
            "en": "🎓 <b>University Admission</b>\n\n✅ Top universities\n✅ Document preparation\n✅ Visa assistance\n✅ Scholarship guidance\n\n📞 Start your education journey!",
            "ru": "🎓 <b>Поступление в Университет</b>\n\n✅ Лучшие университеты\n✅ Подготовка документов\n✅ Помощь с визой\n✅ Стипендии\n\n📞 Начните свое образование!",
            "uz": "🎓 <b>Universitetga Kirish</b>\n\n✅ Top universitetlar\n✅ Hujjat tayyorlash\n✅ Viza yordami\n✅ Grant yo'nalishi\n\n📞 Ta'lim sayohatingizni boshlang!"
        },
        "canton": {
            "en": "🏢 <b>Canton Fair Support</b>\n\n✅ Registration help\n✅ Booth booking\n✅ Interpretation\n✅ Logistics\n\n📞 Make the most of the fair!",
            "ru": "🏢 <b>Кантонская Ярмарка</b>\n\n✅ Помощь с регистрацией\n✅ Бронирование стендов\n✅ Перевод\n✅ Логистика\n\n📞 Получите максимум от ярмарки!",
            "uz": "🏢 <b>Kanton Yarmarkasi</b>\n\n✅ Ro'yxatdan o'tish\n✅ Stend bron qilish\n✅ Tarjimon\n✅ Logistika\n\n📞 Yarmarkadan maksimal foydalaning!"
        },
        "logistics": {
            "en": "🚚 <b>Logistics Services</b>\n\n✅ Air/Sea freight\n✅ Customs clearance\n✅ Warehousing\n✅ Door-to-door delivery\n\n📞 Safe and fast shipping!",
            "ru": "🚚 <b>Логистические Услуги</b>\n\n✅ Авиа/морские перевозки\n✅ Таможенное оформление\n✅ Складирование\n✅ Доставка до двери\n\n📞 Безопасная и быстрая доставка!",
            "uz": "🚚 <b>Logistika Xizmatlari</b>\n\n✅ Havo/Dengiz tashish\n✅ Bojxona rasmiylashtiruvi\n✅ Omborxona\n✅ Uyigacha yetkazish\n\n📞 Xavfsiz va tez yetkazib berish!"
        }
    },
    "contact": {
        "en": "📞 <b>Contact Us:</b>\n\n📱 Phone: +86 123 456 7890\n✉️ Email: info@chinaagent.com\n💬 WeChat: ChinaAgent\n\n🕐 Working hours: 9:00-18:00 (Beijing Time)",
        "ru": "📞 <b>Контакты:</b>\n\n📱 Телефон: +86 123 456 7890\n✉️ Email: info@chinaagent.com\n💬 WeChat: ChinaAgent\n\n🕐 Рабочие часы: 9:00-18:00 (Пекинское время)",
        "uz": "📞 <b>Aloqa:</b>\n\n📱 Telefon: +86 123 456 7890\n✉️ Email: info@chinaagent.com\n💬 WeChat: ChinaAgent\n\n🕐 Ish vaqti: 9:00-18:00 (Pekin vaqti)"
    },
    "pricing": {
        "en": "💼 <b>Our Pricing:</b>\n\n🔤 Translation: From $50\n🔍 Sourcing: 5% of order\n🎓 Admission: $500\n🏢 Canton Fair: Custom\n🚚 Logistics: Based on weight\n\n📝 Send request for detailed quote",
        "ru": "💼 <b>Цены:</b>\n\n🔤 Перевод: От $50\n🔍 Поиск: 5% от заказа\n🎓 Поступление: $500\n🏢 Кантон: Индивидуально\n🚚 Логистика: По весу\n\n📝 Отправьте запрос для детальной оценки",
        "uz": "💼 <b>Narxlar:</b>\n\n🔤 Tarjima: $50 dan\n🔍 Qidirish: Buyurtmaning 5%\n🎓 Kirish: $500\n🏢 Kanton: Maxsus\n🚚 Logistika: Og'irlikka qarab\n\n📝 Batafsil narx uchun so'rov yuboring"
    },
    "about": {
        "en": "ℹ️ <b>About China Agent Bot</b>\n\n🇨🇳 We are your trusted partner for all business activities in China.\n\n✅ 5+ years experience\n✅ 200+ satisfied clients\n✅ Professional team\n✅ 24/7 support\n\n🎯 Making China business easy!",
        "ru": "ℹ️ <b>О China Agent Bot</b>\n\n🇨🇳 Мы - ваш надежный партнер для бизнеса в Китае.\n\n✅ 5+ лет опыта\n✅ 200+ довольных клиентов\n✅ Профессиональная команда\n✅ Поддержка 24/7\n\n🎯 Делаем бизнес с Китаем легким!",
        "uz": "ℹ️ <b>China Agent Bot Haqida</b>\n\n🇨🇳 Biz Xitoydagi biznes uchun ishonchli hamkoringizmiz.\n\n✅ 5+ yil tajriba\n✅ 200+ mamnun mijozlar\n✅ Professional jamoa\n✅ 24/7 qo'llab-quvvatlash\n\n🎯 Xitoy bilan biznesni oson qilamiz!"
    },
    "help": {
        "en": "❓ <b>Help</b>\n\n<b>Commands:</b>\n/start - Restart bot\n/menu - Main menu\n/help - This message\n/contact - Contact info\n/pricing - Our prices\n/about - About us\n\n<b>Tips:</b>\n• Use menu buttons for navigation\n• Send requests anytime\n• Change language in settings",
        "ru": "❓ <b>Помощь</b>\n\n<b>Команды:</b>\n/start - Перезапуск\n/menu - Главное меню\n/help - Это сообщение\n/contact - Контакты\n/pricing - Цены\n/about - О нас\n\n<b>Советы:</b>\n• Используйте кнопки меню\n• Отправляйте запросы в любое время\n• Меняйте язык в настройках",
        "uz": "❓ <b>Yordam</b>\n\n<b>Buyruqlar:</b>\n/start - Qayta boshlash\n/menu - Asosiy menyu\n/help - Bu xabar\n/contact - Aloqa\n/pricing - Narxlar\n/about - Biz haqimizda\n\n<b>Maslahatlar:</b>\n• Menyu tugmalaridan foydalaning\n• Istalgan vaqtda so'rov yuboring\n• Sozlamalarda tilni o'zgartiring"
    },
    "request_prompt": {
        "en": "📝 <b>Send Your Request</b>\n\nPlease describe your needs in detail:\n• Service type\n• Requirements\n• Budget (if applicable)\n• Timeline\n\nWe'll respond within 24 hours!",
        "ru": "📝 <b>Отправить Запрос</b>\n\nОпишите подробно ваши потребности:\n• Тип услуги\n• Требования\n• Бюджет (если есть)\n• Сроки\n\nОтветим в течение 24 часов!",
        "uz": "📝 <b>So'rov Yuborish</b>\n\nEhtiyojlaringizni batafsil tasvirlab bering:\n• Xizmat turi\n• Talablar\n• Byudjet (agar mavjud bo'lsa)\n• Muddat\n\n24 soat ichida javob beramiz!"
    },
    "request_received": {
        "en": "✅ <b>Request Received!</b>\n\nThank you! Our team will contact you within 24 hours.\n\n📞 For urgent matters, call us directly.",
        "ru": "✅ <b>Запрос Получен!</b>\n\nСпасибо! Наша команда свяжется с вами в течение 24 часов.\n\n📞 По срочным вопросам звоните напрямую.",
        "uz": "✅ <b>So'rov Qabul Qilindi!</b>\n\nRahmat! Jamoamiz 24 soat ichida siz bilan bog'lanadi.\n\n📞 Shoshilinch holatlarda to'g'ridan-to'g'ri qo'ng'iroq qiling."
    }
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
    start_text = "👋 Xush kelibsiz! / Добро пожаловать! / Welcome! \n\nIltimos, tilni tanlang / Пожалуйста, выберите язык / Please select your language: "
    await update.message.reply_text(start_text, reply_markup=keyboard, parse_mode="HTML")


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

    logger.info("🤖 China Agent Bot is running on webhook mode...")

    import asyncio, httpx

    async def self_ping():
        url = os.getenv("SELF_URL")
        if not url:
            logger.warning("⚠️ SELF_URL not set, skipping self-ping.")
            return
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    await client.get(url)
                    logger.debug("Pinged self successfully.")
                except Exception as e:
                    logger.error(f"Ping failed: {e}")
                await asyncio.sleep(300)  # every 5 minutes

    async def run_self_ping(app):
        asyncio.create_task(self_ping())

    app.post_init = run_self_ping
    
    

    PORT = int(os.environ.get("PORT", 10000))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )

if __name__ == "__main__":
    main()