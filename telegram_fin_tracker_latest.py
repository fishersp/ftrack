import logging
import os
import sys
from datetime import datetime
from io import BytesIO

import pandas as pd
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import configparser

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    handlers=[
        logging.FileHandler("tracker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ],
)
log = logging.getLogger("fin_tracker")

# Загрузка конфигурации
config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

# Конфигурационные параметры
ALLOWED_USERS = [int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()]
N8N_GET_URL = config["n8n"].get("N8N_GET_URL", "")
N8N_WEBHOOK_URL = config["n8n"].get("N8N_WEBHOOK_URL", "")

# Функция проверки авторизации
def is_auth(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

# Функция нормализации имен столбцов
def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower()
    return df

# Функция получения Excel-файла с Google Drive через n8n
def get_drive_sheet(sheet_name: str) -> pd.DataFrame:
    log.info(f"Запрос Excel-файла с n8n: {N8N_GET_URL}")
    
    try:
        # Отправляем запрос на получение файла
        resp = requests.get(N8N_GET_URL, timeout=30)
        
        # Логируем информацию о запросе
        log.info(f"Статус ответа: {resp.status_code}")
        log.info(f"Content-Type: {resp.headers.get('content-type')}")
        log.info(f"Content-Length: {resp.headers.get('content-length')}")
        
        # Проверяем статус ответа
        if resp.status_code != 200:
            log.error(f"Ошибка при получении файла: статус {resp.status_code}")
            log.error(f"Текст ответа: {resp.text[:200]}")
            raise Exception(f"Ошибка при получении файла: статус {resp.status_code}")
        
        # Проверяем тип контента
        content_type = resp.headers.get('content-type', '')
        if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' not in content_type:
            log.warning(f"Предупреждение: Content-Type не соответствует Excel: {content_type}")
        
        # Сохраняем полученный контент в файл для диагностики
        debug_file = "debug_response.bin"
        with open(debug_file, "wb") as f:
            f.write(resp.content)
        log.info(f"Сохранено {len(resp.content)} байт в {debug_file}")
        
        # Если размер файла слишком мал, это может быть ошибка
        if len(resp.content) < 100:
            log.warning(f"Предупреждение: Получен очень маленький файл ({len(resp.content)} байт)")
            log.warning(f"Первые 100 байт: {resp.content[:100]}")
            
        # Пытаемся прочитать Excel-файл
        try:
            excel_data = BytesIO(resp.content)
            df = pd.read_excel(excel_data, sheet_name=sheet_name, engine="openpyxl")
            log.info(f"Excel-файл успешно прочитан, найден лист '{sheet_name}' с {len(df)} строками")
            return df
        except Exception as e:
            log.error(f"Ошибка при чтении Excel-файла: {str(e)}")
            raise
            
    except Exception as e:
        log.exception(f"Ошибка при получении или обработке файла: {str(e)}")
        raise

# Функция отправки данных в n8n для сохранения в Excel
def upload_to_n8n(file_content: BytesIO, file_name: str, meta: dict | None = None):
    if not N8N_WEBHOOK_URL:
        log.warning("N8N_WEBHOOK_URL не указан.")
        return
        
    try:
        log.info(f"Отправка данных в n8n: {N8N_WEBHOOK_URL}")
        log.info(f"Мета-данные: {meta}")
        
        # Подготовка файла для отправки
        files = {"file": (file_name, file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        
        # Отправка запроса
        resp = requests.post(N8N_WEBHOOK_URL, files=files, data=meta or {}, stream=True, timeout=30)
        
        # Логируем информацию о запросе
        log.info(f"Статус ответа: {resp.status_code}")
        log.info(f"Content-Type: {resp.headers.get('content-type')}")
        
        # Проверяем статус ответа
        if resp.status_code != 200:
            log.error(f"Ошибка при отправке файла: статус {resp.status_code}")
            log.error(f"Текст ответа: {resp.text[:200]}")
            return False
            
        # Пытаемся получить JSON-ответ
        try:
            resp_json = resp.json()
            log.info(f"Ответ JSON: {resp_json}")
        except:
            log.info(f"Ответ текст: {resp.text[:200]}")
            
        return True
    except Exception as e:
        log.exception(f"Ошибка при отправке файла в n8n: {str(e)}")
        return False

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    await update.message.reply_text("Привет!\nОтправь расход: Категория, сумма, комментарий.")

# Обработчик команды /test
async def test_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
        
    await update.message.reply_text("🔄 Тестирую подключение к n8n...")
    
    try:
        # Тестируем GET-запрос
        resp = requests.get(N8N_GET_URL, timeout=10)
        get_status = f"✅ GET: {resp.status_code}, Content-Type: {resp.headers.get('content-type')}, Size: {len(resp.content)} bytes"
    except Exception as e:
        get_status = f"❌ GET: Ошибка - {str(e)}"
    
    try:
        # Тестируем POST-запрос с минимальными данными
        test_data = {"test": "true", "timestamp": str(datetime.now())}
        resp = requests.post(N8N_WEBHOOK_URL, data=test_data, timeout=10)
        post_status = f"✅ POST: {resp.status_code}, Response: {resp.text[:50]}..."
    except Exception as e:
        post_status = f"❌ POST: Ошибка - {str(e)}"
    
    await update.message.reply_text(f"Результаты тестирования:\n\n{get_status}\n\n{post_status}")

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    text = update.message.text.strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return await update.message.reply_text("Формат: Категория, сумма, комментарий")

    category, amount, *comment = parts
    try:
        amount = float(amount.replace("₽", "").replace(" ", ""))
    except ValueError:
        return await update.message.reply_text("Сумма должна быть числом.")
    comment = comment[0] if comment else ""
    date_str = datetime.now().date()

    await update.message.reply_text(f"🔄 Обрабатываю: {category}, {amount:.0f}₽{', ' + comment if comment else ''}...")

    try:
        # Получаем текущий Excel-файл
        log.info("Получение Excel-файла с Google Drive...")
        df_trk = norm_cols(get_drive_sheet("Трекер расходов"))
        log.info(f"Получен Excel-файл с {len(df_trk)} строками")
        
        # Добавляем новую строку
        new_row = {"дата": date_str, "категория": category, "сумма (₽)": amount, "комментарий": comment, "учитывается в анализе?": "да"}
        df_trk = pd.concat([df_trk, pd.DataFrame([new_row])], ignore_index=True)
        log.info(f"Добавлена новая строка, теперь {len(df_trk)} строк")
        
        # Сохраняем DataFrame в BytesIO
        output = BytesIO()
        df_trk.to_excel(output, sheet_name="Трекер расходов", index=False, engine="openpyxl")
        output.seek(0) # Перемещаем указатель в начало потока
        log.info(f"Excel-файл сохранен в BytesIO, размер: {output.getbuffer().nbytes} байт")

        try:
            # Отправляем BytesIO в n8n с правильным именем файла
            meta_data = {"дата": str(date_str), "категория": category, "сумма": f"{amount:.0f}", "комментарий": comment}
            upload_success = upload_to_n8n(output, "Финансовый_план_итоговая_сводка_2.xlsx", meta_data)
            
            if not upload_success:
                log.error("Ошибка при отправке файла в n8n")
                return await update.message.reply_text("❌ Не удалось сохранить данные. Проверьте логи.")
        except Exception as e:
            log.exception(f"Ошибка upload_to_n8n: {str(e)}")
            return await update.message.reply_text(f"❌ Ошибка при сохранении: {str(e)}")
    except Exception as e:
        log.exception(f"Общая ошибка: {str(e)}")
        return await update.message.reply_text(f"❌ Не удалось записать расход или получить файл: {str(e)}")

    log.info(f"Добавлена запись: {category}, {amount:.2f}, {comment}")
    await update.message.reply_text(f"✅ Записано: {category}, {amount:.0f}₽{', ' + comment if comment else ''}")

def main():
    # Создаем и настраиваем бота
    app = ApplicationBuilder().token(config["bot"]["TOKEN"]).build()
    
    # Добавляем обработчики команд и сообщений
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_connection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    log.info("=== Бот запущен ===")
    app.run_polling()

if __name__ == "__main__":
    main()
