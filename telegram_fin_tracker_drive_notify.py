
import logging
import os
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

# --- Логирование ------------------------------------------------
logging.basicConfig(
    filename="tracker.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("fin_tracker")

# --- Конфиг -----------------------------------------------------
config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

EXCEL_PATH = config["bot"].get("EXCEL_PATH", "Финансовый_план_и_долги (9).xlsx")
ALLOWED_USERS = [
    int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()
]
N8N_WEBHOOK_URL = config["bot"].get("N8N_WEBHOOK_URL", "")
N8N_GET_URL = config["bot"].get("N8N_GET_URL", "")

# --- Утилиты ----------------------------------------------------
def is_auth(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower()
    return df

def send_plain_table(update: Update, header: str, lines: list[str]):
    table = "\n".join([header, "-" * len(header), *lines])
    return update.message.reply_text(f"<pre>{table}</pre>", parse_mode="HTML")

def upload_to_n8n(file_path: str, meta: dict = None):
    if not N8N_WEBHOOK_URL or not os.path.exists(file_path):
        log.warning("N8N_WEBHOOK_URL не указан или файл не найден: %s", file_path)
        return
    try:
        with open(file_path, "rb") as f:
            files = {
                "file": (
                    os.path.basename(file_path),
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            }
            response = requests.post(N8N_WEBHOOK_URL, files=files, data=meta or {})
        if response.status_code == 200:
            log.info("✅ Файл успешно отправлен в n8n.")
        else:
            log.warning(
                "⚠️ Ошибка при отправке в n8n: %s | %s",
                response.status_code,
                response.text,
            )
    except Exception:
        log.exception("Ошибка при отправке файла в n8n")

def get_drive_sheet(sheet_name: str) -> pd.DataFrame:
    try:
        if not N8N_GET_URL:
            raise ValueError("Не указан N8N_GET_URL в config.ini")
        resp = requests.post(N8N_GET_URL)
        resp.raise_for_status()
        return pd.read_excel(BytesIO(resp.content), sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        log.exception("Ошибка при получении файла из n8n")
        raise

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
        df_trk = norm_cols(get_drive_sheet("Трекер расходов"))
        new_row = {
            "дата": datetime.now().date(),
            "категория": category,
            "сумма (₽)": amount,
            "комментарий": comment,
            "учитывается в анализе?": "да",
        }
        df_trk = pd.concat([df_trk, pd.DataFrame([new_row])], ignore_index=True)
        df_trk.to_excel(EXCEL_PATH, sheet_name="Трекер расходов", index=False, engine="openpyxl")
        upload_to_n8n(EXCEL_PATH, {
            "дата": str(new_row["дата"]),
            "категория": category,
            "сумма": f"{amount:.0f}",
            "комментарий": comment
        })
    except Exception:
        log.exception("Ошибка записи в Excel")
        return await update.message.reply_text(
            "Не удалось записать расход. Проверьте Excel‑файл или подключение к n8n."
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
    log.info("=== Бот с n8n (Google Drive) запущен ===")
    app.run_polling()

if __name__ == "__main__":
    main()
