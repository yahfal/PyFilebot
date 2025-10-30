import os
import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    MessageHandler,
    filters
)

# Чтение настроек из файла
def load_config():
    config = {}
    try:
        with open('config.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Удаляем кавычки если есть
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    if key == 'ALLOWED_USER_IDS':
                        # Преобразуем строку с ID в список чисел
                        if value:
                            config[key] = [int(user_id.strip()) for user_id in value.split(',')]
                        else:
                            config[key] = []
                    else:
                        config[key] = value
    except FileNotFoundError:
        print("Файл config.txt не найден! Создайте его с настройками.")
        exit(1)
    
    return config

# Загрузка конфигурации
config = load_config()
TOKEN = config.get('TOKEN')
ROOT_PATH = config.get('ROOT_PATH', './files')
ALLOWED_USER_IDS = config.get('ALLOWED_USER_IDS', [])

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def restricted(func):
    """Декоратор для ограничения доступа к обработчикам"""
    @wraps(func)
    async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USER_IDS:
            logger.warning(f"Попытка несанкционированного доступа от user_id: {user_id}")
            if update.message:
                await update.message.reply_text("⛔ Доступ запрещен!")
            elif update.callback_query:
                await update.callback_query.answer("⛔ Доступ запрещен!", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

@restricted
async def start(update: Update, context: CallbackContext) -> None:
    """Обработка команды /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет {user.first_name}\n"
        "Я бот для работы с файлами. Используй /browse чтобы просмотреть файлы и папки."
    )

@restricted
async def handle_document(update: Update, context: CallbackContext) -> None:
    """Обработчик для загрузки файлов"""
    document = update.message.document
    file_name = document.file_name

    current_path = context.user_data.get('current_path', ROOT_PATH)
    file_path = os.path.join(current_path, file_name)

    # Проверяем безопасность пути
    if not is_safe_path(ROOT_PATH, file_path):
        await update.message.reply_text("⚠️ Сохранение в эту папку запрещено!")
        return

    try:
        file = await document.get_file()
        await file.download_to_drive(file_path)
        logger.info(f"Файл '{file_name}' сохранен в '{current_path}' пользователем {update.effective_user.id}")
        await update.message.reply_text(f"✅ Файл '{file_name}' успешно загружен!")
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при загрузке файла.")


def is_safe_path(base_path, target_path):
    """Проверяет, находится ли целевой путь внутри базового пути"""
    base_path = os.path.abspath(base_path)
    target_path = os.path.abspath(target_path)
    return os.path.commonpath([base_path]) == os.path.commonpath([base_path, target_path])

@restricted
async def browse(update: Update, context: CallbackContext, path: str = None) -> None:
    """Показывает содержимое указанной папки с возможностью навигации"""
    current_path_from_callback = path
    if current_path_from_callback is None:
        path = context.user_data.get('current_path', ROOT_PATH)
    else:
        path = current_path_from_callback

    # Проверяем безопасность пути
    if not is_safe_path(ROOT_PATH, path):
        error_msg = "⚠️ Доступ к этой папке запрещен!"
        if update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)
        return
    
    context.user_data['current_path'] = path
    
    try:
        entries = os.listdir(path)
        folders = sorted([e for e in entries if os.path.isdir(os.path.join(path, e))])
        files = sorted([e for e in entries if os.path.isfile(os.path.join(path, e))])
        
        keyboard = []
        for folder in folders:
            keyboard.append([InlineKeyboardButton(f"📁 {folder}", callback_data=f"folder:{folder}")])
        
        for file in files:
            keyboard.append([
                InlineKeyboardButton(f"📄 {file}", callback_data=f"file:{file}"),
                InlineKeyboardButton("🗑️", callback_data=f"delete_request:{file}")
            ])
        
        nav_buttons = []
        if path != ROOT_PATH:
            parent_path = os.path.dirname(path)
            nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"nav:back:{parent_path}"))
            nav_buttons.append(InlineKeyboardButton("🏠 Домой", callback_data=f"nav:home:{ROOT_PATH}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = f"Текущая папка: `{os.path.basename(path) or '/'}`"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
            
    except Exception as e:
        logger.error(f"Ошибка в browse: {e}")
        error_msg = "⚠️ Произошла ошибка!"
        if update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)

async def button_handler(update: Update, context: CallbackContext) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        logger.warning(f"Несанкционированный доступ от user_id: {user_id}")
        await query.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    data = query.data
    current_path = context.user_data.get('current_path', ROOT_PATH)
    
    if data.startswith("folder:"):
        folder_name = data.split(":", 1)[1]
        new_path = os.path.join(current_path, folder_name)
        await browse(update, context, path=new_path)
    
    elif data.startswith("file:"):
        file_name = data.split(":", 1)[1]
        file_path = os.path.join(current_path, file_name)
        if is_safe_path(ROOT_PATH, file_path):
            try:
                await context.bot.send_document(chat_id=query.message.chat_id, document=open(file_path, 'rb'), filename=file_name)
            except Exception as e:
                logger.error(f"Ошибка отправки файла: {e}")
                await query.answer("⚠️ Ошибка при отправке файла", show_alert=True)
    
    elif data.startswith("delete_request:"):
        file_name = data.split(":", 1)[1]
        keyboard = [[
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_confirm:{file_name}"),
            InlineKeyboardButton("❌ Отмена", callback_data="delete_cancel")
        ]]
        await query.edit_message_text(text=f"Удалить '{file_name}'?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("delete_confirm:"):
        file_name = data.split(":", 1)[1]
        file_path = os.path.join(current_path, file_name)
        if is_safe_path(ROOT_PATH, file_path):
            try:
                os.remove(file_path)
                await query.answer(f"Файл '{file_name}' удален.")
                await browse(update, context, path=current_path)
            except Exception as e:
                logger.error(f"Ошибка удаления файла: {e}")
                await query.answer("⚠️ Ошибка при удалении.", show_alert=True)

    elif data.startswith("delete_cancel"):
        await browse(update, context, path=current_path)

    elif data.startswith("nav:"):
        _, action, target_path = data.split(":", 2)
        await browse(update, context, path=target_path)

def main() -> None:
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("browse", browse))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    if not os.path.exists(ROOT_PATH):
        os.makedirs(ROOT_PATH)
        print(f"Создана корневая папка: {ROOT_PATH}")
    main()
