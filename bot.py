import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    Application,
    MessageHandler
)
from telegram.ext import filters

# Настройки
TOKEN = "8116369656:AAF9fP0ieKKcfSju6Y0VB2TecQK5l9ZPlL8"  # Замените на ваш токен
FOLDER_PATH = "./files"   # Путь к папке с файлами

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext) -> None:
    """Обработка команды /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет {user.first_name}!\n"
        "Я бот для работы с файлами. Используй /files чтобы посмотреть доступные файлы."
    )

async def list_files(update: Update, context: CallbackContext) -> None:
    """Показывает список файлов с кнопками"""
    try:
        files = [f for f in os.listdir(FOLDER_PATH) if os.path.isfile(os.path.join(FOLDER_PATH, f))]
        
        if not files:
            await update.message.reply_text("В папке нет файлов.")
            return
            
        keyboard = []
        for file in files:
            keyboard.append([InlineKeyboardButton(file, callback_data=file)])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите файл:", reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Ошибка при чтении папки: {e}")
        await update.message.reply_text("Ошибка при доступе к папке с файлами.")

async def send_file(update: Update, context: CallbackContext) -> None:
    """Отправляет выбранный файл"""
    query = update.callback_query
    await query.answer()
    
    file_name = query.data
    file_path = os.path.join(FOLDER_PATH, file_name)
    
    try:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=open(file_path, 'rb'),
            filename=file_name
        )
    except Exception as e:
        logger.error(f"Ошибка отправки файла: {e}")
        await query.message.reply_text("⚠️ Ошибка при отправке файла")

def main() -> None:
    """Запуск бота"""
    # Создаем Application
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("files", list_files))
    application.add_handler(CallbackQueryHandler(send_file))
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    # Создаем папку для файлов если её нет
    if not os.path.exists(FOLDER_PATH):
        os.makedirs(FOLDER_PATH)
        print(f"Создана папка: {FOLDER_PATH}")
    
    main()