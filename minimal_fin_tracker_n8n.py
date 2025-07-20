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

# --- Конфигурация ---------------------------------------------------------
TOKEN = "7575422774:AAFMZyuxHZ1ArYPE-j2rf94BIC2nBuyVPqk"
ALLOWED_USERS = [272327626]  # замени на свой Telegram user ID
EXCEL_PATH = "C:\\Docs\\tbot\\fin_track\\Финансовый_план_и_долги (9).xlsx"
N8N_WEBHOOK_URL = (
    "https://n8n-fintrack-dreamfish.amvera.io/webhook-test/upload-fin-file"
)

# --- Логирование ----------------------------------------------------------
logging.basicConfig(
    filename="mini_tracker.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("mini_tracker")

# --- Утилиты --------------------------------------------------------------


def is_auth(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower()
    return df


def upload_to_n8n(file_path: str):
    if not os.path.exists(file_path):
        log.warning("Файл не найден: %s", file_path)
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
            response = requests.post(N8N_WEBHOOK_URL, files=files)
        if response.status_code == 200:
            log.info("✅ Файл успешно отправлен в n8n.")
        else:
            log.warning(
                "⚠️ Ошибка при отправке в n8n: %s | %s",
                response.status_code,
                response.text,
            )
    except Exception:
        log.exception("Ошибка отправки файла в n8n")


# --- Бот ------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    await update.message.reply_text("Готов. Отправь: Категория, сумма, комментарий")


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
        if os.path.exists(EXCEL_PATH):
            df_trk = norm_cols(pd.read_excel(EXCEL_PATH, sheet_name="Трекер расходов"))
        else:
            df_trk = pd.DataFrame(
                columns=[
                    "дата",
                    "категория",
                    "сумма (₽)",
                    "комментарий",
                    "учитывается в анализе?",
                ]
            )

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
        ) as writer:
            df_trk.to_excel(writer, sheet_name="Трекер расходов", index=False)

        log.info("🧾 Расход записан: %s, %.2f, %s", category, amount, comment)
        upload_to_n8n(EXCEL_PATH)
    except Exception as e:
        log.exception("Ошибка при записи или отправке.")
        return await update.message.reply_text("Ошибка при записи расхода.")

    await update.message.reply_text(
        f"✅ Записано и отправлено: {category}, {amount:.0f}₽"
    )


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
