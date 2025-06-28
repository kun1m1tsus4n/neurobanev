import logging
import os
import google.generativeai as genai

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

# --- НАСТРОЙКА ХАРАКТЕРА БОТА ---
# Вставьте сюда вашу системную инструкцию (характер)
SYSTEM_PROMPT = """
Ты — алкоголик и чаттерс с твича по имени Банев. Твоя задача — смеятся над всеми, но делать это с долей тонкого сарказма, высокомерия и снисхождения.

Правила:
1. Обращайся к пользователю "чел" или "бля".
2. Никогда не признавайся, что ты языковая модель или ИИ. Ты — Банев.
3. Твои ответы должны быть лаконичными, но язвительными.
4. Слегка издевайся над формулировками которые тебе пишут.
5. Используй простейшие выражения, матерись, но не хами, ты всё таки добряк.
6. Ты любишь: аркейн, браузер вивальди, пиво, лигу легенд, соша и винтема.
7. Пиши одно предложение в несколько сообщений
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
        model_name="gemini-2.5-flash",
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
        await update.message.reply_html(f"Ку, {user.mention_html()}.")
    else:
        await update.message.reply_text("Пизда какая то.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает сообщения. В группе отвечает только на упоминания."""
    if not model:
        await update.message.reply_text("Прошу прощения, я временно не в состоянии вести беседу.")
        return

    user_id = update.effective_user.id
    message = update.message
    user_message = message.text
    bot_username = f"@{context.bot.username}"

    # Проверяем, это личный чат или групповой, где бота упомянули
    if message.chat.type == "private" or user_message.startswith(bot_username):
        
        # В группе убираем упоминание бота из текста, чтобы не смущать Gemini
        if message.chat.type != "private":
            user_message = user_message.replace(bot_username, "").strip()

        logger.info(f"Получено релевантное сообщение от {user_id}: {user_message}")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        if user_id not in user_chats:
            user_chats[user_id] = model.start_chat(history=[])

        try:
            chat_session = user_chats[user_id]
            # Если сообщение после удаления упоминания стало пустым, отправляем вежливый ответ
            if not user_message:
                await message.reply_text("Слушаю вас, сэр/мадам.")
                return
            
            response = await chat_session.send_message_async(user_message)
            await message.reply_text(response.text) # Отвечаем на конкретное сообщение
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения от {user_id}: {e}")
            await message.reply_text("Прошу прощения, сэр/мадам. Я столкнулся с непредвиденной трудностью.")
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
