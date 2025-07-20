"""Telegram‑бот финансового трекера (Google Sheets)
Исправленная версия — корректно работает с APScheduler + pytz.
"""

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
    JobQueue,
    filters,
)
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import configparser

# ---------------------- Логирование ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    handlers=[
        logging.FileHandler("tracker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("fin_tracker")

# ---------------------- Конфиг ---------------------------
BASE_DIR = os.path.dirname(__file__)
config = configparser.ConfigParser()
config.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")

ALLOWED_USERS = [
    int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()
]
SPREADSHEET_ID = config["sheets"]["SPREADSHEET_ID"]
SHEET_NAME = config["sheets"].get("SHEET_NAME", "Трекер расходов")

# ---------------- Google Sheets авторизация --------------
creds = Credentials.from_service_account_file(
    os.path.join(BASE_DIR, "service_account.json"),
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# -------------------- Утилиты ----------------------------
def is_auth(user_id: int) -> bool:
    """Проверяем, разрешён ли пользователь."""
    return user_id in ALLOWED_USERS


# ------------------- Handlers ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    await update.message.reply_text(
        "Привет!\n"
        "Отправь расход сообщением:\n"
        "<категория>, <сумма>, <комментарий>"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    text = (update.message.text or "").strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return await update.message.reply_text(
            "Формат: Категория, сумма, комментарий"
        )

    category, amount, *comment = parts
    # число
    try:
        amount = float(amount.replace("₽", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return await update.message.reply_text("Сумма должна быть числом.")

    comment = comment[0] if comment else ""
    date_str = datetime.now().strftime("%Y-%m-%d")

    await update.message.reply_text(
        f"🔄 Сохраняю: {category}, {amount:.0f}₽{f', {comment}' if comment else ''}…"
    )
    try:
        sheet.append_row([date_str, category, amount, comment, "да"])
        log.info("Добавлена строка: %s, %.2f, %s", category, amount, comment)
        await update.message.reply_text(
            f"✅ Записано: {category}, {amount:.0f}₽{f', {comment}' if comment else ''}"
        )
    except Exception as exc:
        log.exception("Ошибка записи в Google Sheets")
        await update.message.reply_text(f"❌ Ошибка записи: {exc}")


# ------------------- MAIN --------------------------------
def main():
    # pytz‑таймзона для Москвы
    moscow_tz = pytz.timezone("Europe/Moscow")

    # Создаём свой AsyncIOScheduler, где явно задаём timezone → pytz
    scheduler = AsyncIOScheduler(timezone=moscow_tz)
    job_queue = JobQueue(scheduler=scheduler)

    # Application
    app = (
        ApplicationBuilder()
        .token(config["bot"]["TOKEN"])
        .job_queue(job_queue)
        .build()
    )

    # Хэндлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("=== Финансовый бот запущен ===")
    app.run_polling()


if __name__ == "__main__":
    main()