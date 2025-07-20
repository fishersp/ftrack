# telegram_fin_tracker.py
import logging
import pandas as pd
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import configparser

# --- Настройки логирования ---
logging.basicConfig(
    filename="tracker.log",
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Загрузка конффигурации ---
config = configparser.ConfigParser()
config.read("config.ini")
EXCEL_PATH = "C:\Docs\OmenDocs\MyFinance\Финансовый_план_и_долги (8).xlsx"
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
        "Привет! Отправь расход в формате: Категория, сумма, комментарий.\n"
        "Или используй /категории для просмотра лимитов."
    )

# --- Команда /категории ---
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

    response = "\U0001F4C8 Категории расходов:\n"
    for _, row in df_exp.iterrows():
        category = row["Категория"]
        limit = row["Примерная сумма в месяц (₽)"]
        spent = df_period[df_period["Категория"] == category]["Сумма (₽)"].sum()
        remain = limit - spent
        response += f"\n*{category}*\nЛимит: {limit}₽\nПотрачено: {spent:.0f}₽\nОстаток: {remain:.0f}₽\n"

    await update.message.reply_text(response, parse_mode="Markdown")

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

# --- Основная функция ---
def main():
    app = ApplicationBuilder().token(config["bot"]["TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("categories", categories))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
