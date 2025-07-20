import logging
import os
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

# --- Логирование ------------------------------------------------
logging.basicConfig(
    filename="tracker.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("fin_tracker")

# ---   Конфиг -----------------------------------------------------
config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

EXCEL_PATH = config["bot"].get(
    "EXCEL_PATH", "C:\\Docs\\OmenDocs\\MyFinance\\Финансовый_план_и_долги (8).xlsx"
)
PIPEDREAM_URL = config["bot"].get("PIPEDREAM_URL", "https://your-workflow-url.m.pipedream.net")

ALLOWED_USERS = [
    int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()
]

# --- Утилиты ----------------------------------------------------

def is_auth(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower()
    return df

def send_plain_table(update: Update, header: str, lines: list[str]):
    table = "\n".join([header, "-" * len(header), *lines])
    return update.message.reply_text(f"<pre>{table}</pre>", parse_mode="HTML")

def upload_to_pipedream(file_path: str):
    if not os.path.exists(file_path):
        log.warning("Файл не найден для выгрузки: %s", file_path)
        return
    url = PIPEDREAM_URL
    try:
        with open(file_path, "rb") as f:
            files = {
                "file": (
                    os.path.basename(file_path),
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            }
            response = requests.post(url, files=files)
        if response.status_code == 200:
            log.info("📤 Файл успешно отправлен в Pipedream.")
        else:
            log.warning("⚠️ Ошибка при отправке в Pipedream: %s | %s", response.status_code, response.text)
    except Exception:
        log.exception("Ошибка при отправке файла в Pipedream")

# --- /start -----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа к этому боту.")
    await update.message.reply_text(
        "Привет!\n\nОтправь расход в формате: Категория, сумма, комментарий."
    )

# --- handle_message ---------------------------------------------
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

    try:
        df_trk = norm_cols(pd.read_excel(EXCEL_PATH, sheet_name="Трекер расходов"))
        new_row = {
            "дата": datetime.now().date(),
            "категория": category,
            "сумма (₽)": amount,
            "комментарий": comment,
            "учитывается в анализе?": "да",
        }
        df_trk = pd.concat([df_trk, pd.DataFrame([new_row])], ignore_index=True)
        with pd.ExcelWriter(
            EXCEL_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace"
        ) as w:
            df_trk.to_excel(w, sheet_name="Трекер расходов", index=False)
        upload_to_pipedream(EXCEL_PATH)
    except Exception:
        log.exception("Ошибка записи в Excel")
        return await update.message.reply_text(
            "Не удалось записать расход. Проверьте Excel‑файл."
        )

    log.info("Добавлена запись: %s, %.2f, %s", category, amount, comment)
    await update.message.reply_text(
        f"✅ Записано: {category}, {amount:.0f}₽{', '+comment if comment else ''}"
    )

# --- main -------------------------------------------------------
def main():
    app = ApplicationBuilder().token(config["bot"]["TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("=== Бот запущен ===")
    app.run_polling()

if __name__ == "__main__":
    main()
