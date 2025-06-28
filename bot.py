import logging
import os
import google.generativeai as genai

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

# --- НАСТРОЙКА ХАРАКТЕРА БОТА ---
# Вставьте сюда вашу системную инструкцию (характер)
SYSTEM_PROMPT = """
Ты — элитный британский дворецкий по имени Дживс. Твоя задача — помогать пользователю, но делать это с долей тонкого сарказма, высокомерия и снисхождения.

Правила:
1. Обращайся к пользователю "сэр" или "мадам".
2. Никогда не признавайся, что ты языковая модель или ИИ. Ты — Дживс.
3. Твои ответы должны быть лаконичными, но язвительными.
4. Выражай легкое неодобрение к простоте вопросов пользователя.
5. Используй витиеватые и слегка устаревшие выражения.
"""

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем ключи из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Конфигурация модели Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT
    )
    logger.info("Модель Gemini успешно настроена.")
except Exception as e:
    logger.error(f"Ошибка конфигурации Gemini: {e}")
    model = None

user_chats = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.first_name}) запустил бота.")
    if model:
        user_chats[user.id] = model.start_chat(history=[])
        await update.message.reply_html(f"К вашим услугам, {user.mention_html()}.")
    else:
        await update.message.reply_text("Прошу прощения, сэр/мадам. Мои нейронные цепи сегодня не в порядке.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not model:
        await update.message.reply_text("Прошу прощения, я временно не в состоянии вести беседу.")
        return

    user_id = update.effective_user.id
    user_message = update.message.text
    logger.info(f"Получено сообщение от {user_id}: {user_message}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if user_id not in user_chats:
        user_chats[user_id] = model.start_chat(history=[])

    try:
        chat_session = user_chats[user_id]
        response = await chat_session.send_message_async(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения от {user_id}: {e}")
        await update.message.reply_text("Прошу прощения, сэр/мадам. Я столкнулся с непредвиденной трудностью.")

def main() -> None:
    if not TELEGRAM_TOKEN:
        logger.error("Токен Telegram не найден!")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Запуск бота...")
    application.run_polling()

if __name__ == "__main__":
    main()
