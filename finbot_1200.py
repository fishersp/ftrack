import logging
import os
import sys
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
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

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    handlers=[
        logging.FileHandler("tracker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("fin_tracker")

# Загружаем конфиг из текущей директории
config_path = os.path.join(os.path.dirname(__file__), "config.ini")
config = configparser.ConfigParser()
config.read(config_path, encoding="utf-8")

ALLOWED_USERS = [
    int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()
]
SPREADSHEET_ID = config["sheets"]["SPREADSHEET_ID"]
SHEET_NAME = config["sheets"].get("SHEET_NAME", "Трекер расходов")

# Авторизация Google
creds = Credentials.from_service_account_file(
    os.path.join(os.path.dirname(__file__), "service_account.json"),
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


# Проверка авторизации
def is_auth(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    await update.message.reply_text(
        "Привет! Отправь расход: Категория, сумма, комментарий"
    )


# Сообщения
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

    await update.message.reply_text(
        f"🔄 Обрабатываю: {category}, {amount:.0f}₽{', ' + comment if comment else ''}..."
    )

    try:
        row = [date_str, category, amount, comment, "да"]
        sheet.append_row(row)
        await update.message.reply_text(
            f"✅ Записано: {category}, {amount:.0f}₽{', ' + comment if comment else ''}"
        )
        log.info(f"Добавлена строка: {row}")
    except Exception as e:
        log.exception("Ошибка при записи в Google Sheets")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


# Бот
def main():
    app = ApplicationBuilder().token(config["bot"]["TOKEN"]).build()
    app.job_queue.scheduler.configure(timezone=pytz_timezone("Europe/Moscow"))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("=== Бот с Google Sheets API запущен ===")
    app.run_polling()


if __name__ == "__main__":
    main()
