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
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]  # Add admin user IDs

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

# Texts
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
        "uz": "🛠 *Bizning Xizmatlarimiz*\n\n"
              "Quyidagi xizmatlardan birini tanlang:",
        "ru": "🛠 *Наши Услуги*\n\n"
              "Выберите одну из услуг:",
        "en": "🛠 *Our Services*\n\n"
              "Choose one of the services:",
    },
    "service_details": {
        "translation": {
            "uz": "🔤 *Tarjima Xizmati*\n\n"
                  "📋 Taqdim etamiz:\n"
                  "• Biznes uchrashuv tarjimalari\n"
                  "• Hujjat tarjimalari (kontrakt, sertifikat)\n"
                  "• Telefon tarjimalari\n"
                  "• Video konferensiya tarjimalari\n\n"
                  "💰 Narx: $20-30/soat\n"
                  "⏱ Davomiyligi: Sizning ehtiyojingizga ko'ra\n"
                  "🌐 Tillar: Xitoy ↔️ O'zbek/Rus/Ingliz\n\n"
                  "✅ Professional tarjimonlar\n"
                  "✅ Biznes tajribasi\n"
                  "✅ Maxfiylik kafolati",
            "ru": "🔤 *Услуга Перевода*\n\n"
                  "📋 Предоставляем:\n"
                  "• Переводы деловых встреч\n"
                  "• Переводы документов (контракты, сертификаты)\n"
                  "• Телефонные переводы\n"
                  "• Переводы видеоконференций\n\n"
                  "💰 Цена: $20-30/час\n"
                  "⏱ Длительность: По вашим потребностям\n"
                  "🌐 Языки: Китайский ↔️ Узбекский/Русский/Английский\n\n"
                  "✅ Профессиональные переводчики\n"
                  "✅ Бизнес-опыт\n"
                  "✅ Гарантия конфиденциальности",
            "en": "🔤 *Translation Service*\n\n"
                  "📋 We provide:\n"
                  "• Business meeting translations\n"
                  "• Document translations (contracts, certificates)\n"
                  "• Phone translations\n"
                  "• Video conference translations\n\n"
                  "💰 Price: $20-30/hour\n"
                  "⏱ Duration: According to your needs\n"
                  "🌐 Languages: Chinese ↔️ Uzbek/Russian/English\n\n"
                  "✅ Professional translators\n"
                  "✅ Business experience\n"
                  "✅ Confidentiality guarantee",
        },
        "sourcing": {
            "uz": "🔍 *Mahsulot Qidirish*\n\n"
                  "📋 Xizmatlar:\n"
                  "• Ishonchli fabrika qidirish\n"
                  "• Narx muzokaralari\n"
                  "• Sifat nazorati\n"
                  "• Namuna tekshirish\n"
                  "• Fabrika tashrifi tashkil etish\n\n"
                  "💰 Narx: $100-300 (mahsulot turiga bog'liq)\n"
                  "⏱ Muddat: 3-7 kun\n\n"
                  "✅ 1000+ fabrika bazasi\n"
                  "✅ Eng yaxshi narxlar\n"
                  "✅ Sifat kafolati",
            "ru": "🔍 *Поиск Товаров*\n\n"
                  "📋 Услуги:\n"
                  "• Поиск надежных фабрик\n"
                  "• Переговоры о ценах\n"
                  "• Контроль качества\n"
                  "• Проверка образцов\n"
                  "• Организация визитов на фабрики\n\n"
                  "💰 Цена: $100-300 (зависит от типа товара)\n"
                  "⏱ Срок: 3-7 дней\n\n"
                  "✅ База из 1000+ фабрик\n"
                  "✅ Лучшие цены\n"
                  "✅ Гарантия качества",
            "en": "🔍 *Product Sourcing*\n\n"
                  "📋 Services:\n"
                  "• Finding reliable factories\n"
                  "• Price negotiations\n"
                  "• Quality control\n"
                  "• Sample inspection\n"
                  "• Factory visit organization\n\n"
                  "💰 Price: $100-300 (depends on product type)\n"
                  "⏱ Timeline: 3-7 days\n\n"
                  "✅ 1000+ factory database\n"
                  "✅ Best prices\n"
                  "✅ Quality guarantee",
        },
        "admission": {
            "uz": "🎓 *O'qishga Kirishda Yordam*\n\n"
                  "📋 Yordam beramiz:\n"
                  "• Universitet tanlash\n"
                  "• Hujjatlar tayyorlash\n"
                  "• Stipendiya topish\n"
                  "• Viza jarayoni\n"
                  "• Turar joy topish\n\n"
                  "💰 Narx: $300-500\n"
                  "⏱ Muddat: 1-2 oy\n\n"
                  "✅ 50+ universitet bilan hamkorlik\n"
                  "✅ 90% muvaffaqiyat darajasi\n"
                  "✅ To'liq qo'llab-quvvatlash",
            "ru": "🎓 *Помощь с Поступлением*\n\n"
                  "📋 Помогаем с:\n"
                  "• Выбор университета\n"
                  "• Подготовка документов\n"
                  "• Поиск стипендий\n"
                  "• Визовый процесс\n"
                  "• Поиск жилья\n\n"
                  "💰 Цена: $300-500\n"
                  "⏱ Срок: 1-2 месяца\n\n"
                  "✅ Партнерство с 50+ университетами\n"
                  "✅ 90% успешность\n"
                  "✅ Полная поддержка",
            "en": "🎓 *Admission Help*\n\n"
                  "📋 We help with:\n"
                  "• University selection\n"
                  "• Document preparation\n"
                  "• Scholarship search\n"
                  "• Visa process\n"
                  "• Accommodation search\n\n"
                  "💰 Price: $300-500\n"
                  "⏱ Timeline: 1-2 months\n\n"
                  "✅ Partnership with 50+ universities\n"
                  "✅ 90% success rate\n"
                  "✅ Full support",
        },
        "canton": {
            "uz": "🏢 *Kanton Yarmarkasi*\n\n"
                  "📋 Xizmatlar:\n"
                  "• Yarmarkaga tayyorgarlik\n"
                  "• Tarjima xizmati\n"
                  "• Eksponentlar bilan tanishish\n"
                  "• Namunalar tanlash\n"
                  "• Transport va mehmonxona\n\n"
                  "💰 Narx: $150/kun\n"
                  "⏱ Muddat: Sizning rejangizga ko'ra\n\n"
                  "✅ Yarmarkada 10+ yillik tajriba\n"
                  "✅ Professional tarjimon\n"
                  "✅ To'liq logistika",
            "ru": "🏢 *Кантонская Ярмарка*\n\n"
                  "📋 Услуги:\n"
                  "• Подготовка к ярмарке\n"
                  "• Услуги перевода\n"
                  "• Знакомство с экспонентами\n"
                  "• Выбор образцов\n"
                  "• Транспорт и отель\n\n"
                  "💰 Цена: $150/день\n"
                  "⏱ Срок: По вашему плану\n\n"
                  "✅ 10+ лет опыта на ярмарке\n"
                  "✅ Профессиональный переводчик\n"
                  "✅ Полная логистика",
            "en": "🏢 *Canton Fair*\n\n"
                  "📋 Services:\n"
                  "• Fair preparation\n"
                  "• Translation services\n"
                  "• Meeting exhibitors\n"
                  "• Sample selection\n"
                  "• Transport and hotel\n\n"
                  "💰 Price: $150/day\n"
                  "⏱ Duration: According to your plan\n\n"
                  "✅ 10+ years fair experience\n"
                  "✅ Professional translator\n"
                  "✅ Full logistics",
        },
        "business": {
            "uz": "💼 *Biznes Yo'lboshchi*\n\n"
                  "📋 Maslahatlar:\n"
                  "• Bozor tahlili\n"
                  "• Biznes rejalashtirish\n"
                  "• Sheriklar topish\n"
                  "• Kompaniya ochish\n"
                  "• Yuridik maslahat\n\n"
                  "💰 Narx: $100/soat\n"
                  "⏱ Muddat: Sizning ehtiyojingizga ko'ra\n\n"
                  "✅ Tajribali maslahatchilar\n"
                  "✅ Xitoy bozori bilimi\n"
                  "✅ O'zbek biznes bilan tajriba",
            "ru": "💼 *Бизнес-Гид*\n\n"
                  "📋 Консультации:\n"
                  "• Анализ рынка\n"
                  "• Бизнес-планирование\n"
                  "• Поиск партнеров\n"
                  "• Открытие компании\n"
                  "• Юридические консультации\n\n"
                  "💰 Цена: $100/час\n"
                  "⏱ Срок: По вашим потребностям\n\n"
                  "✅ Опытные консультанты\n"
                  "✅ Знание китайского рынка\n"
                  "✅ Опыт с узбекским бизнесом",
            "en": "💼 *Business Guide*\n\n"
                  "📋 Consultations:\n"
                  "• Market analysis\n"
                  "• Business planning\n"
                  "• Partner search\n"
                  "• Company registration\n"
                  "• Legal advice\n\n"
                  "💰 Price: $100/hour\n"
                  "⏱ Duration: According to your needs\n\n"
                  "✅ Experienced consultants\n"
                  "✅ Chinese market knowledge\n"
                  "✅ Experience with Uzbek business",
        },
        "logistics": {
            "uz": "🚚 *Logistika Xizmati*\n\n"
                  "📋 Yetkazib berish:\n"
                  "• Havo yuk tashish\n"
                  "• Dengiz yuk tashish\n"
                  "• Avtomobil yuk tashish\n"
                  "• Temir yo'l yuk tashish\n"
                  "• Bojxona rasmiylashtiruvi\n\n"
                  "💰 Narx: Hajm va yo'nalishga bog'liq\n"
                  "⏱ Muddat: 7-30 kun\n\n"
                  "✅ Eng yaxshi tarif\n"
                  "✅ Xavfsiz yetkazib berish\n"
                  "✅ Yukni kuzatish",
            "ru": "🚚 *Услуга Логистики*\n\n"
                  "📋 Доставка:\n"
                  "• Авиаперевозки\n"
                  "• Морские перевозки\n"
                  "• Автомобильные перевозки\n"
                  "• Железнодорожные перевозки\n"
                  "• Таможенное оформление\n\n"
                  "💰 Цена: Зависит от объема и направления\n"
                  "⏱ Срок: 7-30 дней\n\n"
                  "✅ Лучшие тарифы\n"
                  "✅ Безопасная доставка\n"
                  "✅ Отслеживание груза",
            "en": "🚚 *Logistics Service*\n\n"
                  "📋 Delivery:\n"
                  "• Air freight\n"
                  "• Sea freight\n"
                  "• Road freight\n"
                  "• Rail freight\n"
                  "• Customs clearance\n\n"
                  "💰 Price: Depends on volume and destination\n"
                  "⏱ Timeline: 7-30 days\n\n"
                  "✅ Best rates\n"
                  "✅ Safe delivery\n"
                  "✅ Cargo tracking",
        },
    },
    "contact": {
        "uz": "📞 *Biz bilan bog'lanish:*\n\n"
              "👤 Agent: Zhang Wei\n"
              "📱 WeChat: chinaagent_gz\n"
              "✈️ Telegram: @ChinaAgentGZ\n"
              "☎️ Telefon: +86 138 0258 8888\n"
              "📧 Email: info@chinaagent.com\n"
              "🏢 Manzil: Guangzhou, Tianhe District\n\n"
              "⏰ Ish vaqti: 09:00-18:00 (Beijing vaqti)\n"
              "🌐 Veb-sayt: www.chinaagent.com",
        "ru": "📞 *Свяжитесь с нами:*\n\n"
              "👤 Агент: Zhang Wei\n"
              "📱 WeChat: chinaagent_gz\n"
              "✈️ Telegram: @ChinaAgentGZ\n"
              "☎️ Телефон: +86 138 0258 8888\n"
              "📧 Email: info@chinaagent.com\n"
              "🏢 Адрес: Гуанчжоу, район Тяньхэ\n\n"
              "⏰ Рабочие часы: 09:00-18:00 (Пекинское время)\n"
              "🌐 Веб-сайт: www.chinaagent.com",
        "en": "📞 *Contact Us:*\n\n"
              "👤 Agent: Zhang Wei\n"
              "📱 WeChat: chinaagent_gz\n"
              "✈️ Telegram: @ChinaAgentGZ\n"
              "☎️ Phone: +86 138 0258 8888\n"
              "📧 Email: info@chinaagent.com\n"
              "🏢 Address: Guangzhou, Tianhe District\n\n"
              "⏰ Working hours: 09:00-18:00 (Beijing Time)\n"
              "🌐 Website: www.chinaagent.com",
    },
    "pricing": {
        "uz": "💼 *Narxlar:*\n\n"
              "🔹 Tarjima: $20-30/soat\n"
              "🔹 Mahsulot qidirish: $100-300\n"
              "🔹 Kanton yarmarkasi: $150/kun\n"
              "🔹 Biznes konsultatsiya: $100/soat\n"
              "🔹 O'qishga yordam: $300-500\n"
              "🔹 Logistika: Hajmga bog'liq\n\n"
              "💳 To'lov usullari:\n"
              "• WeChat Pay\n"
              "• Alipay\n"
              "• Bank transfer\n"
              "• PayPal\n\n"
              "📝 Aniq narx uchun bog'laning!",
        "ru": "💼 *Цены:*\n\n"
              "🔹 Переводы: $20-30/час\n"
              "🔹 Поиск товаров: $100-300\n"
              "🔹 Кантонская ярмарка: $150/день\n"
              "🔹 Бизнес консультация: $100/час\n"
              "🔹 Помощь с поступлением: $300-500\n"
              "🔹 Логистика: Зависит от объема\n\n"
              "💳 Способы оплаты:\n"
              "• WeChat Pay\n"
              "• Alipay\n"
              "• Банковский перевод\n"
              "• PayPal\n\n"
              "📝 Свяжитесь для точной цены!",
        "en": "💼 *Pricing:*\n\n"
              "🔹 Translation: $20-30/hour\n"
              "🔹 Product sourcing: $100-300\n"
              "🔹 Canton Fair: $150/day\n"
              "🔹 Business consultation: $100/hour\n"
              "🔹 Admission help: $300-500\n"
              "🔹 Logistics: Depends on volume\n\n"
              "💳 Payment methods:\n"
              "• WeChat Pay\n"
              "• Alipay\n"
              "• Bank transfer\n"
              "• PayPal\n\n"
              "📝 Contact for exact pricing!",
    },
    "about": {
        "uz": "ℹ *China Agent Bot haqida:*\n\n"
              "🤖 Biz Guanchjoudagi professional agentlar jamoasimiz.\n\n"
              "📊 Bizning ko'rsatkichlar:\n"
              "📅 Tajriba: 8+ yil\n"
              "👥 Mijozlar: 2000+\n"
              "🏢 Hamkor fabrikalar: 1000+\n"
              "🎓 Universitet hamkorliklari: 50+\n"
              "🌏 Tillar: O'zbek, Rus, Ingliz, Xitoy\n\n"
              "✅ Ishonchli va sifatli xizmat!\n"
              "✅ Shaffof narxlar!\n"
              "✅ 24/7 qo'llab-quvvatlash!",
        "ru": "ℹ *О China Agent Bot:*\n\n"
              "🤖 Мы команда профессиональных агентов в Гуанчжоу.\n\n"
              "📊 Наши показатели:\n"
              "📅 Опыт: 8+ лет\n"
              "👥 Клиенты: 2000+\n"
              "🏢 Партнерские фабрики: 1000+\n"
              "🎓 Партнерство с университетами: 50+\n"
              "🌏 Языки: Узбекский, Русский, Английский, Китайский\n\n"
              "✅ Надежный и качественный сервис!\n"
              "✅ Прозрачные цены!\n"
              "✅ Поддержка 24/7!",
        "en": "ℹ *About China Agent Bot:*\n\n"
              "🤖 We are a team of professional agents in Guangzhou.\n\n"
              "📊 Our metrics:\n"
              "📅 Experience: 8+ years\n"
              "👥 Clients: 2000+\n"
              "🏢 Partner factories: 1000+\n"
              "🎓 University partnerships: 50+\n"
              "🌏 Languages: Uzbek, Russian, English, Chinese\n\n"
              "✅ Reliable and quality service!\n"
              "✅ Transparent pricing!\n"
              "✅ 24/7 support!",
    },
    "help": {
        "uz": "❓ *Yordam:*\n\n"
              "📱 *Asosiy buyruqlar:*\n"
              "🔹 /start - Botni qayta ishga tushirish\n"
              "🔹 /menu - Asosiy menyu\n"
              "🔹 /contact - Aloqa ma'lumotlari\n"
              "🔹 /help - Yordam\n\n"
              "💡 *Qanday foydalanish:*\n"
              "1️⃣ Tilni tanlang\n"
              "2️⃣ Kerakli xizmatni ko'ring\n"
              "3️⃣ So'rov yuboring\n"
              "4️⃣ Biz siz bilan bog'lanamiz!\n\n"
              "📝 Savolingiz bo'lsa, tugmalardan foydalaning!",
        "ru": "❓ *Помощь:*\n\n"
              "📱 *Основные команды:*\n"
              "🔹 /start - Перезапустить бота\n"
              "🔹 /menu - Главное меню\n"
              "🔹 /contact - Контактная информация\n"
              "🔹 /help - Помощь\n\n"
              "💡 *Как использовать:*\n"
              "1️⃣ Выберите язык\n"
              "2️⃣ Просмотрите нужную услугу\n"
              "3️⃣ Отправьте запрос\n"
              "4️⃣ Мы свяжемся с вами!\n\n"
              "📝 Если у вас есть вопросы, используйте кнопки!",
        "en": "❓ *Help:*\n\n"
              "📱 *Main commands:*\n"
              "🔹 /start - Restart bot\n"
              "🔹 /menu - Main menu\n"
              "🔹 /contact - Contact information\n"
              "🔹 /help - Help\n\n"
              "💡 *How to use:*\n"
              "1️⃣ Choose language\n"
              "2️⃣ View the service you need\n"
              "3️⃣ Send a request\n"
              "4️⃣ We'll contact you!\n\n"
              "📝 If you have questions, use the buttons!",
    },
    "request_prompt": {
        "uz": "📝 *So'rov yuborish*\n\n"
              "Iltimos, quyidagilarni kiriting:\n"
              "• Xizmat turi\n"
              "• Batafsil ma'lumot\n"
              "• Telefon raqami\n\n"
              "Misol:\n"
              "Tarjima xizmati kerak\n"
              "2-3 kun, biznes uchrashuv\n"
              "+998 90 123 45 67",
        "ru": "📝 *Отправить запрос*\n\n"
              "Пожалуйста, укажите:\n"
              "• Тип услуги\n"
              "• Подробная информация\n"
              "• Номер телефона\n\n"
              "Пример:\n"
              "Нужна услуга перевода\n"
              "2-3 дня, деловая встреча\n"
              "+998 90 123 45 67",
        "en": "📝 *Send Request*\n\n"
              "Please provide:\n"
              "• Service type\n"
              "• Detailed information\n"
              "• Phone number\n\n"
              "Example:\n"
              "Need translation service\n"
              "2-3 days, business meeting\n"
              "+998 90 123 45 67",
    },
    "request_received": {
        "uz": "✅ *So'rov qabul qilindi!*\n\n"
              "Rahmat! Sizning so'rovingiz qabul qilindi.\n"
              "Tez orada siz bilan bog'lanamiz.\n\n"
              "📞 Shoshilinch holatlarda:\n"
              "Telegram: @ChinaAgentGZ\n"
              "WeChat: chinaagent_gz",
        "ru": "✅ *Запрос получен!*\n\n"
              "Спасибо! Ваш запрос принят.\n"
              "Мы свяжемся с вами в ближайшее время.\n\n"
              "📞 В срочных случаях:\n"
              "Telegram: @ChinaAgentGZ\n"
              "WeChat: chinaagent_gz",
        "en": "✅ *Request Received!*\n\n"
              "Thank you! Your request has been received.\n"
              "We will contact you soon.\n\n"
              "📞 For urgent cases:\n"
              "Telegram: @ChinaAgentGZ\n"
              "WeChat: chinaagent_gz",
    },
    "lang_changed": {
        "uz": "🌏 Til muvaffaqiyatli o'zgartirildi!",
        "ru": "🌏 Язык успешно изменен!",
        "en": "🌏 Language changed successfully!",
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

# Service buttons
def get_service_buttons(lang):
    services = {
        "uz": [
            [InlineKeyboardButton("🔤 Tarjima", callback_data="srv_translation")],
            [InlineKeyboardButton("🔍 Mahsulot qidirish", callback_data="srv_sourcing")],
            [InlineKeyboardButton("🎓 O'qishga yordam", callback_data="srv_admission")],
            [InlineKeyboardButton("🏢 Kanton yarmarkasi", callback_data="srv_canton")],
            [InlineKeyboardButton("💼 Biznes yo'lboshchi", callback_data="srv_business")],
            [InlineKeyboardButton("🚚 Logistika", callback_data="srv_logistics")],
        ],
        "ru": [
            [InlineKeyboardButton("🔤 Переводы", callback_data="srv_translation")],
            [InlineKeyboardButton("🔍 Поиск товаров", callback_data="srv_sourcing")],
            [InlineKeyboardButton("🎓 Помощь с поступлением", callback_data="srv_admission")],
            [InlineKeyboardButton("🏢 Кантонская ярмарка", callback_data="srv_canton")],
            [InlineKeyboardButton("💼 Бизнес-гид", callback_data="srv_business")],
            [InlineKeyboardButton("🚚 Логистика", callback_data="srv_logistics")],
        ],
        "en": [
            [InlineKeyboardButton("🔤 Translation", callback_data="srv_translation")],
            [InlineKeyboardButton("🔍 Product Sourcing", callback_data="srv_sourcing")],
            [InlineKeyboardButton("🎓 Admission Help", callback_data="srv_admission")],
            [InlineKeyboardButton("🏢 Canton Fair", callback_data="srv_canton")],
            [InlineKeyboardButton("💼 Business Guide", callback_data="srv_business")],
            [InlineKeyboardButton("🚚 Logistics", callback_data="srv_logistics")],
        ],
    }
    return InlineKeyboardMarkup(services[lang])

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    
    if user_id not in user_languages:
        update_stats("total_users")
    
    keyboard = ReplyKeyboardMarkup(LANG_BUTTONS, resize_keyboard=True)
    msg = (
        "👋 *China Agent Bot* 🇨🇳\n\n"
        "🇺🇿 Xush kelibsiz! Iltimos, tilni tanlang.\n"
        "🇷🇺 Добро пожаловать! Пожалуйста, выберите язык.\n"
        "🇬🇧 Welcome! Please choose your language."
    )
   
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="HTML")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    lang = get_user_lang(user_id)
    text = {"uz": "📋 Asosiy menyu", "ru": "📋 Главное меню", "en": "📋 Main menu"}
    await update.message.reply_text(text[lang], reply_markup=get_menu_markup(lang))

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS["contact"][lang], parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS["help"][lang], parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    
    msg = (
        "📊 *Bot Statistics*\n\n"
        f"👥 Total Users: {bot_stats.get('total_users', 0)}\n"
        f"💬 Total Messages: {bot_stats.get('total_messages', 0)}\n"
        f"📝 Service Requests: {bot_stats.get('service_requests', 0)}\n\n"
        f"🌐 *Users by Language:*\n"
        f"🇺🇿 Uzbek: {bot_stats.get('users_by_lang', {}).get('uz', 0)}\n"
        f"🇷🇺 Russian: {bot_stats.get('users_by_lang', {}).get('ru', 0)}\n"
        f"🇬🇧 English: {bot_stats.get('users_by_lang', {}).get('en', 0)}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# Handle service request conversation
async def request_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    lang = get_user_lang(user_id)
    await update.message.reply_text(TEXTS["request_prompt"][lang], parse_mode="Markdown")
    return WAITING_FOR_REQUEST

async def request_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user = update.message.from_user
    lang = get_user_lang(user_id)
    
    # Save request
    request = {
        "user_id": user_id,
        "username": user.username or "N/A",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "message": update.message.text,
        "timestamp": datetime.now().isoformat(),
        "language": lang
    }
    service_requests.append(request)
    save_json(REQUESTS_FILE, service_requests)
    update_stats("service_requests")
    
    # Notify admins
    admin_msg = (
        f"📝 *New Service Request*\n\n"
        f"👤 User: {user.first_name} {user.last_name or ''}\n"
        f"🆔 ID: {user_id}\n"
        f"📱 Username: @{user.username or 'N/A'}\n"
        f"🌐 Language: {lang.upper()}\n\n"
        f"💬 Message:\n{update.message.text}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    await update.message.reply_text(
        TEXTS["request_received"][lang], 
        parse_mode="Markdown",
        reply_markup=get_menu_markup(lang)
    )
    return ConversationHandler.END

async def request_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    lang = get_user_lang(user_id)
    text = {"uz": "❌ Bekor qilindi", "ru": "❌ Отменено", "en": "❌ Cancelled"}
    await update.message.reply_text(text[lang], reply_markup=get_menu_markup(lang))
    return ConversationHandler.END

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.message.from_user.id)
    lang = get_user_lang(user_id)
    
    update_stats("total_messages")
    
    # Language selection
    if text in ["🇬🇧 English", "🇷🇺 Русский", "🇺🇿 O'zbek"]:
        old_lang = user_languages.get(user_id)
        
        if text == "🇬🇧 English":
            user_languages[user_id] = "en"
        elif text == "🇷🇺 Русский":
            user_languages[user_id] = "ru"
        else:
            user_languages[user_id] = "uz"
        
        new_lang = user_languages[user_id]
        
        # Update language stats
        if old_lang != new_lang:
            if old_lang:
                bot_stats.setdefault("users_by_lang", {})[old_lang] = \
                    bot_stats.get("users_by_lang", {}).get(old_lang, 1) - 1
            bot_stats.setdefault("users_by_lang", {})[new_lang] = \
                bot_stats.get("users_by_lang", {}).get(new_lang, 0) + 1
        
        save_json(LANG_FILE, user_languages)
        save_json(STATS_FILE, bot_stats)
        
        await update.message.reply_text(
            TEXTS["lang_changed"][new_lang], 
            reply_markup=get_menu_markup(new_lang)
        )
        return
    
    # Menu actions
    if text in ["🛠 Services", "🛠 Услуги", "🛠 Xizmatlar"]:
        await update.message.reply_text(
            TEXTS["services_intro"][lang],
            parse_mode="Markdown",
            reply_markup=get_service_buttons(lang)
        )
    elif text in ["📞 Contact", "📞 Контакт", "📞 Aloqa"]:
        await update.message.reply_text(TEXTS["contact"][lang], parse_mode="Markdown")
    elif text in ["💼 Pricing", "💼 Цены", "💼 Narxlar"]:
        await update.message.reply_text(TEXTS["pricing"][lang], parse_mode="Markdown")
    elif text in ["ℹ About", "ℹ О боте", "ℹ Haqida"]:
        await update.message.reply_text(TEXTS["about"][lang], parse_mode="Markdown")
    elif text in ["❓ Help", "❓ Помощь", "❓ Yordam"]:
        await update.message.reply_text(TEXTS["help"][lang], parse_mode="Markdown")
    elif text in ["🌏 Language", "🌏 Язык", "🌏 Til"]:
        keyboard = ReplyKeyboardMarkup(LANG_BUTTONS, resize_keyboard=True)
        msg = {"uz": "🌏 Tilni tanlang:", "ru": "🌏 Выберите язык:", "en": "🌏 Choose a language:"}
        await update.message.reply_text(msg[lang], reply_markup=keyboard)
    elif text in ["📝 Send Request", "📝 Отправить запрос", "📝 So'rov yuborish"]:
        await request_start(update, context)
    else:
        msg = {
            "uz": "❓ Buyruq tushunilmadi. Iltimos, tugmalardan foydalaning:",
            "ru": "❓ Команда не распознана. Пожалуйста, используйте кнопки:",
            "en": "❓ Command not recognized. Please use the buttons:"
        }
        await update.message.reply_text(msg[lang], reply_markup=get_menu_markup(lang))

# Callback handler for inline buttons
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

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Main function
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Request conversation handler
    request_handler = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Regex("^(📝 Send Request|📝 Отправить запрос|📝 So'rov yuborish)$"),
            request_start
        )],
        states={
            WAITING_FOR_REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, request_receive)],
        },
        fallbacks=[CommandHandler("cancel", request_cancel)],
    )
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("contact", contact_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(request_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    logger.info("🤖 Enhanced China Agent Bot is running...")
    logger.info(f"📊 Total users: {bot_stats.get('total_users', 0)}")
    logger.info(f"💬 Total messages: {bot_stats.get('total_messages', 0)}")
    logger.info(f"📝 Service requests: {bot_stats.get('service_requests', 0)}")
    
    app.run_polling()

if __name__ == "__main__":
    main()