"""Telegram‑бот финансового трекера (Google Sheets)
Версия с полным патчем tzlocal → pytz + apscheduler.util.get_localzone
"""

import logging
import os
import sys
from datetime import datetime

# --- Telegram / Google Sheets ---------------------------------
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

# --- Таймзоны и патчи -----------------------------------------
import pytz
import tzlocal
from functools import lru_cache
import apscheduler.util as _aps_util

@lru_cache()
def _pytz_localzone():
    """Возвращаем локальную таймзону как объект pytz, а не zoneinfo."""
    return pytz.timezone(tzlocal.get_localzone_name())

# Патчим и tzlocal, и уже импортированный в APScheduler util.get_localzone
tzlocal.get_localzone = _pytz_localzone
_aps_util.get_localzone = _pytz_localzone

# ----------------------- Логирование --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    handlers=[
        logging.FileHandler("tracker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("fin_tracker")

# ------------------------- Конфиг -----------------------------
BASE_DIR = os.path.dirname(__file__)
import configparser
config = configparser.ConfigParser()
config.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")

ALLOWED_USERS = [
    int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()
]
SPREADSHEET_ID = config["sheets"]["SPREADSHEET_ID"]
SHEET_NAME = config["sheets"].get("SHEET_NAME", "Трекер расходов")

# ------------------ Google Sheets API -------------------------
creds = Credentials.from_service_account_file(
    os.path.join(BASE_DIR, "service_account.json"),
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# --------------------- Утилиты --------------------------------
def is_auth(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

# --------------------- Handlers -------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    await update.message.reply_text(
        "Привет! Отправь расход: <категория>, <сумма>, <комментарий>"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    text = (update.message.text or "").strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return await update.message.reply_text("Формат: Категория, сумма, комментарий")

    category, amount, *comment = parts
    try:
        amount = float(amount.replace("₽", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return await update.message.reply_text("Сумма должна быть числом.")

    comment = comment[0] if comment else ""
    date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        sheet.append_row([date_str, category, amount, comment, "да"])
        await update.message.reply_text(
            f"✅ Записано: {category}, {amount:.0f}₽{f', {comment}' if comment else ''}"
        )
        log.info("Добавлена строка: %s, %.2f, %s", category, amount, comment)
    except Exception as exc:
        log.exception("Ошибка записи в Google Sheets")
        await update.message.reply_text(f"❌ Ошибка записи: {exc}")

# ----------------------- MAIN ---------------------------------
def main():
    tz = pytz.timezone("Europe/Moscow")

    app = (
        ApplicationBuilder()
        .token(config["bot"]["TOKEN"])
        .timezone(tz)   # передаём pytz‑таймзону
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("=== Финансовый бот запущен ===")
    app.run_polling()

if __name__ == "__main__":
    main()