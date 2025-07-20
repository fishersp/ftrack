
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

logging.basicConfig(
    filename="tracker.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("fin_tracker")

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

# EXCEL_PATH is no longer needed as we interact directly with n8n
# EXCEL_PATH = config["bot"].get("EXCEL_PATH", "Финансовый_план_и_долги (9).xlsx")
ALLOWED_USERS = [int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()]
N8N_GET_URL = config["n8n"].get("N8N_GET_URL", "")
N8N_WEBHOOK_URL = config["n8n"].get("N8N_WEBHOOK_URL", "")

def is_auth(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower()
    return df

def get_drive_sheet(sheet_name: str) -> pd.DataFrame:
    resp = requests.get(N8N_GET_URL, timeout=30)
    print("DEBUG get-sheet: status =", resp.status_code)
    print("DEBUG content-type =", resp.headers.get("content-type"))
    print("DEBUG first 120 bytes =", resp.content[:120])
    resp.raise_for_status()
    return pd.read_excel(BytesIO(resp.content), sheet_name=sheet_name, engine="openpyxl")

def upload_to_n8n(file_content: BytesIO, file_name: str, meta: dict | None = None):
    if not N8N_WEBHOOK_URL:
        log.warning("N8N_WEBHOOK_URL не указан.")
        return
    try:
        files = {"file": (file_name, file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        requests.post(N8N_WEBHOOK_URL, files=files, data=meta or {}, stream=True, timeout=30)
    except Exception:
        log.exception("Ошибка при отправке файла в n8n")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    await update.message.reply_text("Привет!\nОтправь расход: Категория, сумма, комментарий.")

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

    try:
        df_trk = norm_cols(get_drive_sheet("Трекер расходов"))
        new_row = {"дата": date_str, "категория": category, "сумма (₽)": amount, "комментарий": comment, "учитывается в анализе?": "да"}
        df_trk = pd.concat([df_trk, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save the DataFrame to an in-memory BytesIO object
        output = BytesIO()
        df_trk.to_excel(output, sheet_name="Трекер расходов", index=False, engine="openpyxl")
        output.seek(0) # Rewind to the beginning of the stream

        try:
            # Upload the BytesIO object to n8n with the correct filename
            upload_to_n8n(output, "Финансовый_план_итоговая_сводка_2.xlsx", {"дата": str(date_str), "категория": category, "сумма": f"{amount:.0f}", "комментарий": comment})
        except Exception:
            log.exception("Ошибка upload_to_n8n")
    except Exception:
        log.exception("Ошибка записи/отправки")
        return await update.message.reply_text("Не удалось записать расход или получить файл.")

    log.info("Добавлена запись: %s, %.2f, %s", category, amount, comment)
    await update.message.reply_text(f"✅ Записано: {category}, {amount:.0f}₽{\', \' + comment if comment else \'\'}")

def main():
    app = ApplicationBuilder().token(config["bot"]["TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("=== Бот запущен ===")
    app.run_polling()

if __name__ == "__main__":
    main()


