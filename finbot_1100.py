import logging
import os
import sys
from datetime import datetime

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
from pytz import timezone as pytz_timezone

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

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    await update.message.reply_text("Привет!\nОтправь расход: Категория, сумма, комментарий.")

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
    date_str = datetime.now().strftime("%Y-%m-%d")

    await update.message.reply_text(f"🔄 Обрабатываю: {category}, {amount:.0f}₽{', ' + comment if comment else ''}...")

    # Подготавливаем данные для отправки в n8n
    payload = {
        "дата": date_str,
        "категория": category,
        "сумма": f"{amount:.0f}",
        "комментарий": comment
    }

    try:
        # Отправляем POST-запрос на webhook
        log.info(f"Отправляю данные: {payload}")
        response = requests.post(N8N_WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            await update.message.reply_text(f"✅ Записано: {category}, {amount:.0f}₽{', ' + comment if comment else ''}")
        else:
            log.error(f"Ошибка сохранения данных: {response.status_code} - {response.text[:200]}")
            await update.message.reply_text("❌ Не удалось записать расход. Проверьте логи.")
    except Exception as e:
        log.exception(f"Ошибка при отправке данных в n8n: {str(e)}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# Тестовая функция (если нужно)
async def test_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    try:
        # Тестируем GET-запрос
        resp = requests.get(N8N_GET_URL, timeout=10)
        get_status = f"✅ GET: {resp.status_code}, Size: {len(resp.content)} bytes"
    except Exception as e:
        get_status = f"❌ GET: Ошибка - {str(e)}"

    await update.message.reply_text(f"Результаты тестирования:\n\n{get_status}")

def main():
    # Создаем и настраиваем бота
    app = ApplicationBuilder().token(config["bot"]["TOKEN"]).build()

    # Устанавливаем временную зону для JobQueue
    app.job_queue.scheduler.configure(timezone=pytz_timezone('Europe/Moscow'))

    # Добавляем обработчики команд и сообщений
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_connection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    log.info("=== Бот запущен ===")
    app.run_polling()

if __name__ == "__main__":
    main()