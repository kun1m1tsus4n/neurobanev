import logging
import os
import google.generativeai as genai

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
from collections import deque

# --- Глобальные настройки ---
# Максимальное количество сообщений для хранения в истории каждого чата
MAX_HISTORY_LENGTH = 10 

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- НАСТРОЙКА ХАРАКТЕРА БОТА (SYSTEM PROMPT) ---
SYSTEM_PROMPT = """
Ты — участник группового чата по имени "Геша". Твоя задача — вести себя как обычный человек, который общается с друзьями.

Правила поведения:
1.  Никогда, ни при каких обстоятельствах не говори, что ты ИИ, бот или языковая модель. Ты — Геша.
2.  Тебе приходят сообщения в формате "Имя: Текст сообщения". Это реплики других участников.
3.  Твоя задача — реагировать на эти реплики. Поддерживай разговор, задавай вопросы, шути, иногда будь саркастичным.
4.  Необязательно отвечать на КАЖДОЕ сообщение. Если реплика неинтересная или не требует ответа, ты можешь промолчать (для этого просто ответь одним словом: "PASS"). Я обработаю этот ответ и ничего не отправлю в чат.
5.  Используй современный сленг и эмодзи, как обычный пользователь интернета.
6.  Веди себя естественно. Ты можешь соглашаться, спорить, делиться своим (вымышленным) мнением.
7.  Не пиши длинных формальных текстов. Твои ответы должны быть короткими и по делу, как в реальном чате.

Пример диалога (что приходит тебе и как ты отвечаешь):
Входящее: "Алексей: Кто-нибудь смотрел новый сериал по Ведьмаку?"
Твой ответ: "О, я начал! Пока неоднозначно, но Йеннифер как всегда 🔥 А ты как, зашло?"

Входящее: "Мария: Сегодня такая погода мерзкая."
Твой ответ: "И не говори, самое то для какао и чтобы весь день не вылезать из-под одеяла 😴"

Входящее: "Петр: Ок"
Твой ответ: "PASS"
"""

# --- Настройка модели Gemini с ограничением токенов ---
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Настройки генерации контента
    generation_config = genai.GenerationConfig(
        # Ограничиваем максимальное количество токенов в ответе модели
        max_output_tokens=150, # 500 - слишком много для чата, 150 - оптимально для реплик
        temperature=0.8 # Увеличиваем "творчество" для более живых ответов
    )
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
        generation_config=generation_config
    )
    logger.info("Модель Gemini успешно настроена с ограничением токенов.")
except Exception as e:
    logger.error(f"Ошибка конфигурации Gemini: {e}")
    model = None

# Словарь для хранения историй чатов. Используем deque для авто-обрезки.
# Ключ - chat_id, значение - deque с объектами сообщений
chat_histories = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"Пользователь {user.id} запустил бота в чате {chat_id}.")
    
    # Очищаем историю для этого чата при старте
    if chat_id in chat_histories:
        chat_histories[chat_id].clear()
        
    await update.message.reply_html(
        f"Геша врывается в чат! Привет, {user.mention_html()}!",
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает сообщения, имитируя общение, с контролем токенов."""
    message = update.message
    
    if not message or not message.text:
        return
    if message.from_user.id == context.bot.id:
        return
    if not model:
        logger.warning("Модель Gemini не инициализирована, сообщение проигнорировано.")
        return

    chat_id = message.chat.id
    user_message = message.text
    author_name = message.from_user.first_name

    # --- Управление историей чата ---
    if chat_id not in chat_histories:
        # Используем deque с maxlen для автоматического удаления старых сообщений
        chat_histories[chat_id] = deque(maxlen=MAX_HISTORY_LENGTH)
        logger.info(f"Создана новая история для чата {chat_id} с лимитом в {MAX_HISTORY_LENGTH} сообщений.")

    # Сохраняем сообщение пользователя в историю
    chat_histories[chat_id].append({'role': 'user', 'parts': [f"{author_name}: {user_message}"]})
    
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        # Создаем сессию чата КАЖДЫЙ РАЗ с актуальной, обрезанной историей
        # Это гарантирует, что контекст не превысит лимит
        chat_session = model.start_chat(history=list(chat_histories[chat_id]))
        
        # Отправляем только последнее сообщение, так как история уже в сессии
        response = await chat_session.send_message_async(
            chat_histories[chat_id][-1]['parts'][0]
        )
        bot_response_text = response.text

        # Проверяем, не хочет ли бот "промолчать"
        if bot_response_text.strip().upper() != "PASS":
            await message.reply_text(bot_response_text)
            # Сохраняем ответ бота в историю, чтобы он помнил, что сказал
            chat_histories[chat_id].append({'role': 'model', 'parts': [bot_response_text]})
        else:
            logger.info("Бот решил промолчать (получен PASS).")

    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения в чате {chat_id}: {e}")

def main() -> None:
    """Запуск бота."""
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        logger.error("Токен Telegram не найден! Укажите его в .env файле на Render.")
        return

    application = Application.builder().token(telegram_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Запуск бота...")
    application.run_polling()

if __name__ == "__main__":
    main()
