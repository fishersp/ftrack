# telegram_fin_tracker.py
import logging
import pandas as pd
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import configparser
import os

# --- Настройки логирования ---
logging.basicConfig(
    filename="tracker.log",
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Загрузка конфигурации ---
config = configparser.ConfigParser()
config.read("config.ini")
EXCEL_PATH = config["bot"].get("EXCEL_PATH", "Финансовый_план_и_долги (8).xlsx")
if not os.path.exists(EXCEL_PATH):
    raise FileNotFoundError(f"Excel-файл не найден: {EXCEL_PATH}")

ALLOWED_USERS = [int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()]

# --- Проверка доступа ---
def is_authorized(user_id):
    return user_id in ALLOWED_USERS

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return

    await update.message.reply_text(
        "Привет! Отправь расход в формате: Категория, сумма, комментарий."
        "Или используй /categories для просмотра лимитов."
    )

# --- Команда /categories ---
async def categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return

    df_exp = pd.read_excel(EXCEL_PATH, sheet_name="Расходы")
    df_tr = pd.read_excel(EXCEL_PATH, sheet_name="Трекер расходов", parse_dates=["Дата"])

    today = datetime.today()
    start_date = datetime(today.year, today.month, 4)
    if today.day < 4:
        start_date = datetime(today.year, today.month - 1, 4)
    end_date = datetime(start_date.year, start_date.month + 1, 4)

    df_period = df_tr[(df_tr["Дата"] >= start_date) & (df_tr["Дата"] < end_date) & (df_tr["Учитывается в анализе?"] == "Да")]

    table_lines = ["Категория         | Лимит | Потрачено | Остаток", "------------------|--------|-----------|--------"]
    total_limit = 0
    total_spent = 0

    for _, row in df_exp.iterrows():
        category = row["Категория"]
        if category.strip().lower() == "итого":
            continue
        limit = row["Примерная сумма в месяц (₽)"] or 0
        spent = df_period[df_period["Категория"] == category]["Сумма (₽)"].sum()
        remain = limit - spent
        total_limit += limit
        total_spent += spent
        table_lines.append(f"{category[:18]:<18} | {limit:6.0f} | {spent:9.0f} | {remain:7.0f}")

    total_remain = total_limit - total_spent
    table_lines.append("----------------------------------------------")
    table_lines.append(f"ИТОГО             | {total_limit:6.0f} | {total_spent:9.0f} | {total_remain:7.0f}")

    table_lines.append("----------------------------------")
total_sum = sum([row["Примерная сумма в месяц (₽)"] or 0 for _, row in df.iterrows() if str(row["Категория"]).strip().lower() != "итого"])
table_lines.append(f"ИТОГО             | {total_sum:6.0f} |")
response = "\n".join(table_lines)
    await update.message.reply_text(f"<pre>{response}</pre>", parse_mode="HTML")

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return

    text = update.message.text.strip()
    parts = [p.strip() for p in text.split(",")]

    if len(parts) < 2:
        await update.message.reply_text("Пожалуйста, введи расход в формате: Категория, сумма, комментарий")
        return

    try:
        category = parts[0]
        amount = float(parts[1].replace("₽", "").strip())
        comment = parts[2] if len(parts) > 2 else ""

        new_row = pd.DataFrame.from_dict([{
            "Дата": datetime.today().date(),
            "Категория": category,
            "Сумма (₽)": amount,
            "Комментарий": comment,
            "Учитывается в анализе?": "Да"
        }])

        df = pd.read_excel(EXCEL_PATH, sheet_name="Трекер расходов")
        df = pd.concat([df, new_row], ignore_index=True)
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name="Трекер расходов", index=False)

        logger.info(f"{update.effective_user.username} добавил: {category}, {amount}₽, {comment}")
        await update.message.reply_text(f"✅ Записано: {category}, {amount}₽, {comment}")

    except Exception as e:
        logger.error(e)
        await update.message.reply_text("Ошибка при обработке. Проверь формат.")

# --- Команда /month_plan ---
async def month_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return

    df = pd.read_excel(EXCEL_PATH, sheet_name="Расходы")
    table_lines = ["Категория         | Сумма  | Обязательный", "------------------|--------|--------------"]
    for _, row in df.iterrows():
        category = row["Категория"]
        if category.strip().lower() == "итого":
            continue
        amount = row["Примерная сумма в месяц (₽)"] or 0
        required = row["Обязательный расход?"] or ""
        table_lines.append(f"{category[:18]:<18} | {amount:6.0f} | {required:<12}")

    table_lines.append("----------------------------------")
total_sum = sum([row["Примерная сумма в месяц (₽)"] or 0 for _, row in df.iterrows() if str(row["Категория"]).strip().lower() != "итого"])
table_lines.append(f"ИТОГО             | {total_sum:6.0f} |")
response = "\n".join(table_lines)
    await update.message.reply_text(f"<pre>{response}</pre>", parse_mode="HTML")

# --- Команда /accounts ---
async def accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
        return

    df = pd.read_excel(EXCEL_PATH, sheet_name="Остатки по счетам")
    table_lines = ["Банк        | Тип         | Остаток", "------------|-------------|--------"]
    for _, row in df.iterrows():
        bank = row["Банк"]
        acc_type = row["Тип"]
        balance = row["Остаток"]
        table_lines.append(f"{bank[:12]:<12} | {acc_type[:11]:<11} | {balance:7.2f}")

    table_lines.append("----------------------------------")
total_sum = sum([row["Примерная сумма в месяц (₽)"] or 0 for _, row in df.iterrows() if str(row["Категория"]).strip().lower() != "итого"])
table_lines.append(f"ИТОГО             | {total_sum:6.0f} |")
response = "\n".join(table_lines)
    await update.message.reply_text(f"<pre>{response}</pre>", parse_mode="HTML")

# --- Основная функция ---
def main():
    app = ApplicationBuilder().token(config["bot"]["TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("categories", categories))
    app.add_handler(CommandHandler("month_plan", month_plan))
    app.add_handler(CommandHandler("accounts", accounts))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
