import json
import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

LANG_FILE = "user_lang.json"

# 🌍 Load saved user languages (if file exists)
if os.path.exists(LANG_FILE):
    with open(LANG_FILE, "r", encoding="utf-8") as f:
        user_languages = json.load(f)
else:
    user_languages = {}

TEXTS = {
    "start": {
        "uz": "👋 *China Agent Bot* ga xush kelibsiz! Iltimos, tilni tanlang:",
        "ru": "👋 Добро пожаловать в *China Agent Bot*! Пожалуйста, выберите язык:",
        "en": "👋 Welcome to *China Agent Bot*! Please choose your language:",
    },
    "menu": {
        "uz": [["🛠 Xizmatlar", "📞 Aloqa"], ["🌏 Til", "ℹ Haqida"]],
        "ru": [["🛠 Услуги", "📞 Контакт"], ["🌏 Язык", "ℹ О боте"]],
        "en": [["🛠 Services", "📞 Contact"], ["🌏 Language", "ℹ About"]],
    },
    "services": {
        "uz": "1️⃣ Tarjima\n2️⃣ Mahsulot topish\n3️⃣ O‘qishga kirishda yordam\n4️⃣ Kanton yarmarkasi\n5️⃣ Biznes yo‘lboshchi",
        "ru": "1️⃣ Переводы\n2️⃣ Поиск товаров\n3️⃣ Помощь с поступлением\n4️⃣ Кантонская ярмарка\n5️⃣ Бизнес-гид",
        "en": "1️⃣ Translation\n2️⃣ Product sourcing\n3️⃣ Admission help\n4️⃣ Canton Fair\n5️⃣ Business guide",
    },
    "contact": {
        "uz": "📞 Aloqa:\nWeChat: your_wechat\nTelegram: @yourusername\nTelefon: +86 123456789",
        "ru": "📞 Контакт:\nWeChat: your_wechat\nTelegram: @yourusername\nТелефон: +86 123456789",
        "en": "📞 Contact:\nWeChat: your_wechat\nTelegram: @yourusername\nPhone: +86 123456789",
    },
    "about": {
        "uz": "🤖 China Agent Bot sizga Guanchjoudagi ishonchli agentlar bilan bog‘lanishda yordam beradi.",
        "ru": "🤖 China Agent Bot помогает вам связаться с надежными агентами в Гуанчжоу.",
        "en": "🤖 China Agent Bot helps connect with trusted agents in Guangzhou.",
    },
    "lang_choice": {
        "uz": "🌏 Tilni tanlang:",
        "ru": "🌏 Выберите язык:",
        "en": "🌏 Choose a language:",
    },
}

LANG_BUTTONS = [["🇺🇿 O‘zbek", "🇷🇺 Русский", "🇬🇧 English"]]


def save_languages():
    with open(LANG_FILE, "w", encoding="utf-8") as f:
        json.dump(user_languages, f, ensure_ascii=False, indent=2)


def get_user_lang(user_id):
    return user_languages.get(str(user_id), "en")


def get_menu_markup(lang):
    return ReplyKeyboardMarkup(TEXTS["menu"][lang], resize_keyboard=True)


# 🔹 /start — show all 3 languages
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(LANG_BUTTONS, resize_keyboard=True)
    msg = (
        "👋 *China Agent Bot* 🇨🇳\n\n"
        "🇺🇿 Xush kelibsiz! Iltimos, tilni tanlang.\n"
        "🇷🇺 Добро пожаловать! Пожалуйста, выберите язык.\n"
        "🇬🇧 Welcome! Please choose your language."
    )
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")


# 🔹 Handle user messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.message.from_user.id)
    lang = get_user_lang(user_id)

    # 🌍 Language selection
    if text in ["🇬🇧 English", "🇷🇺 Русский", "🇺🇿 O‘zbek"]:
        if text == "🇬🇧 English":
            user_languages[user_id] = "en"
        elif text == "🇷🇺 Русский":
            user_languages[user_id] = "ru"
        else:
            user_languages[user_id] = "uz"

        save_languages()
        lang = get_user_lang(user_id)
        await update.message.reply_text(TEXTS["lang_choice"][lang], reply_markup=get_menu_markup(lang))
        return

    # 🧭 Menu actions
    if text in ["🛠 Services", "🛠 Услуги", "🛠 Xizmatlar"]:
        await update.message.reply_text(TEXTS["services"][lang])
    elif text in ["📞 Contact", "📞 Контакт", "📞 Aloqa"]:
        await update.message.reply_text(TEXTS["contact"][lang])
    elif text in ["ℹ About", "ℹ О боте", "ℹ Haqida"]:
        await update.message.reply_text(TEXTS["about"][lang])
    elif text in ["🌏 Language", "🌏 Язык", "🌏 Til"]:
        keyboard = ReplyKeyboardMarkup(LANG_BUTTONS, resize_keyboard=True)
        await update.message.reply_text(TEXTS["lang_choice"][lang], reply_markup=keyboard)
    else:
        await update.message.reply_text(TEXTS["lang_choice"][lang], reply_markup=get_menu_markup(lang))


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Multilingual bot with memory is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
