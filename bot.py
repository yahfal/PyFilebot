import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext
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
                    
                    config[key] = value
    except FileNotFoundError:
        print("Файл config.txt не найден! Создайте его с настройками.")
        exit(1)
    
    return config

# Загрузка конфигурации
config = load_config()
TOKEN = config.get('TOKEN')
ROOT_PATH = config.get('ROOT_PATH', './files')

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
        f"Привет {user.first_name}\n"
        "Я бот для работы с файлами. Используй /browse чтобы просмотреть файлы и папки."
    )

def is_safe_path(base_path, target_path):
    """Проверяет, находится ли целевой путь внутри базового пути"""
    base_path = os.path.abspath(base_path)
    target_path = os.path.abspath(target_path)
    return os.path.commonpath([base_path]) == os.path.commonpath([base_path, target_path])

async def browse(update: Update, context: CallbackContext, path: str = None) -> None:
    """Показывает содержимое указанной папки с возможностью навигации"""
    if path is None:
        path = ROOT_PATH
    
    # Проверяем безопасность пути
    if not is_safe_path(ROOT_PATH, path):
        error_msg = "⚠️ Доступ к этой папке запрещен!"
        if update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)
        return
    
    # Сохраняем текущий путь в user_data
    context.user_data['current_path'] = path
    
    try:
        # Получаем список файлов и папок
        entries = os.listdir(path)
        folders = []
        files = []
        
        for entry in entries:
            full_path = os.path.join(path, entry)
            try:
                # Пытаемся проверить тип файла/папки
                if os.path.isdir(full_path):
                    folders.append(entry)
                elif os.path.isfile(full_path):
                    files.append(entry)
            except PermissionError:
                logger.warning(f"Нет доступа к элементу: {full_path}")
            except Exception as e:
                logger.error(f"Ошибка при проверке элемента {full_path}: {e}")
        
        # Создаем клавиатуру
        keyboard = []
        
        # Кнопки для папок
        for folder in sorted(folders):
            keyboard.append([
                InlineKeyboardButton(f"📁 {folder}", 
                callback_data=f"folder:{folder}")
            ])
        
        # Кнопки для файлов
        for file in sorted(files):
            keyboard.append([
                InlineKeyboardButton(f"📄 {file}", 
                callback_data=f"file:{file}")
            ])
        
        # Кнопки навигации в последнем ряду
        nav_buttons = []
        
        # Кнопка "Назад" (если не в корневой папке)
        if path != ROOT_PATH:
            parent_path = os.path.dirname(path)
            nav_buttons.append(
                InlineKeyboardButton("◀️ Назад", callback_data=f"nav:back:{parent_path}")
            )
        
        # Кнопка "Домой" (всегда кроме корневой папки)
        if path != ROOT_PATH:
            nav_buttons.append(
                InlineKeyboardButton("🏠 Домой", callback_data=f"nav:home:{ROOT_PATH}")
            )
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Текст сообщения
        message_text = f"Текущая папка: {path}"
        
        # Обновляем существующее сообщение или отправляем новое
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup
            )
            
    except PermissionError:
        error_msg = "⛔ Нет доступа к этой папке!"
        if update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)
    except FileNotFoundError:
        error_msg = "❌ Папка не найдена!"
        if update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        error_msg = "⚠️ Произошла непредвиденная ошибка!"
        if update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)

async def button_handler(update: Update, context: CallbackContext) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    current_path = context.user_data.get('current_path', ROOT_PATH)
    
    if data.startswith("folder:"):
        # Переход в папку
        folder_name = data.split(":", 1)[1]
        new_path = os.path.join(current_path, folder_name)
        await browse(update, context, path=new_path)
    
    elif data.startswith("file:"):
        # Отправка выбранного файла
        file_name = data.split(":", 1)[1]
        file_path = os.path.join(current_path, file_name)
        
        try:
            # Проверяем безопасность пути перед отправкой
            if not is_safe_path(ROOT_PATH, file_path):
                await query.answer("⚠️ Доступ к этому файлу запрещен!", show_alert=True)
                return
            
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=open(file_path, 'rb'),
                filename=file_name
            )
            await query.answer(f"Файл {file_name} отправлен!")
        except PermissionError:
            await query.answer("⛔ Нет доступа к этому файлу!", show_alert=True)
        except FileNotFoundError:
            await query.answer("❌ Файл не найден!", show_alert=True)
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            await query.answer("⚠️ Ошибка при отправке файла", show_alert=True)
    
    elif data.startswith("nav:"):
        # Обработка навигационных кнопок
        action = data.split(":", 2)[1]
        target_path = data.split(":", 2)[2]
        await browse(update, context, path=target_path)

def main() -> None:
    """Запуск бота"""
    # Создаем Application
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("browse", browse))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    # Создаем корневую папку если её нет
    if not os.path.exists(ROOT_PATH):
        os.makedirs(ROOT_PATH)
        print(f"Создана корневая папка: {ROOT_PATH}")
    
    main()