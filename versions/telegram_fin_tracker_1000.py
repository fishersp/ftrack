# telegram_fin_tracker.py – 🪙 личный финансовый трекер в Telegram
# ---------------------------------------------------------------
# Ключевые изменения этой версии (2025‑06‑05)
# 1. Исправлен NameError в /categories (df → df_exp)
# 2. Нормализуем заголовки столбцов Excel (strip + lower) – меньше ошибок
# 3. Таблицы выводятся ровно: один разделитель (---) между заголовком и данными.
# 4. /month_plan показывает ИТОГО.
# 5. /accounts – автоматический поиск колонок «Банк», «Тип», «Остаток» (регистронезависимо);
#    если не найдено – читабельное сообщение.
# 6. Больше логов и try/except → проще отладка.
# ---------------------------------------------------------------

import logging
import os
from datetime import datetime

import pandas as pd
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
if not os.path.exists(EXCEL_PATH):
    raise FileNotFoundError(f"Excel‑файл не найден: {EXCEL_PATH}")

ALLOWED_USERS = [
    int(x) for x in config["bot"].get("ALLOWED_USERS", "").split(",") if x.strip()
]

# --- Утилиты ----------------------------------------------------


def is_auth(user_id: int) -> bool:
    """Проверяем, есть ли пользователь в белом списке."""
    return user_id in ALLOWED_USERS


def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Удаляем пробелы и делаем lower у заголовков."""
    df.columns = df.columns.str.strip().str.lower()
    return df


def send_plain_table(update: Update, header: str, lines: list[str]):
    """Удобный вывод моноширинной таблицы через <pre>."""
    table = "\n".join([header, "-" * len(header), *lines])
    return update.message.reply_text(f"<pre>{table}</pre>", parse_mode="HTML")


# --- /start -----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа к этому боту.")

    await update.message.reply_text(
        "Привет!\n\nОтправь расход в формате: Категория, сумма, комментарий.\n"
        "Полезные команды:\n"
        "  /categories – баланс по категориям за текущий расч. месяц\n"
        "  /month_plan – план расходов на месяц\n"
        "  /accounts – остатки по счетам"
    )


# --- /categories -----------------------------------------------
async def categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    try:
        df_exp = norm_cols(pd.read_excel(EXCEL_PATH, sheet_name="Расходы"))
        df_trk = norm_cols(
            pd.read_excel(
                EXCEL_PATH, sheet_name="Трекер расходов", parse_dates=["Дата"]
            )
        )
    except Exception as e:
        log.exception("Ошибка чтения Excel")
        return await update.message.reply_text(
            "Не удалось прочитать Excel‑файл. Проверь путь и листы."
        )

    today = datetime.now()
    start_date = datetime(today.year, today.month, 4)
    if today.day < 4:
        # сдвиг на предыдущий месяц
        start_date = datetime(today.year, today.month - 1, 4)
    next_month = start_date.replace(day=28) + pd.Timedelta(days=4)  # безопасный переход
    end_date = next_month.replace(day=4)

    df_period = df_trk[
        (df_trk["дата"] >= start_date)
        & (df_trk["дата"] < end_date)
        & (df_trk["учитывается в анализе?"] == "да")
    ]

    header = "Категория               | Лимит | Потрачено | Остаток"
    lines: list[str] = []
    total_limit = total_spent = 0.0

    for _, row in df_exp.iterrows():
        cat = str(row.get("категория", "")).strip()
        if cat.lower() == "итого" or not cat:
            continue
        limit = float(row.get("примерная сумма в месяц (₽)", 0) or 0)
        spent = float(df_period[df_period["категория"] == cat]["сумма (₽)"].sum())
        remain = limit - spent
        total_limit += limit
        total_spent += spent
        lines.append(f"{cat[:22]:<22} | {limit:6.0f} | {spent:9.0f} | {remain:7.0f}")

    lines.extend(
        (
            "".ljust(len(header), "-"),
            f"ИТОГО                   | {total_limit:6.0f} | {total_spent:9.0f} | {total_limit - total_spent:7.0f}",
        )
    )
    await send_plain_table(update, header, lines)


# --- /month_plan -----------------------------------------------
async def month_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    try:
        df_exp = norm_cols(pd.read_excel(EXCEL_PATH, sheet_name="Расходы"))
    except Exception:
        log.exception("Ошибка чтения Excel (month_plan)")
        return await update.message.reply_text("Не удалось прочитать Excel‑файл.")

    header = "Категория               | План, ₽ | Обязат.?"
    lines: list[str] = []
    total_sum = 0.0

    for _, row in df_exp.iterrows():
        cat = str(row.get("категория", "")).strip()
        if cat.lower() == "итого" or not cat:
            continue
        amount = float(row.get("примерная сумма в месяц (₽)", 0) or 0)
        total_sum += amount
        required = str(row.get("обязательный расход?", "")).strip()
        lines.append(f"{cat[:22]:<22} | {amount:7.0f} | {required:<8}")

    lines.extend(
        (
            "".ljust(len(header), "-"),
            f"ИТОГО                   | {total_sum:7.0f} |        ",
        )
    )
    await send_plain_table(update, header, lines)


# --- /accounts --------------------------------------------------
async def accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_auth(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    try:
        df_acc = norm_cols(pd.read_excel(EXCEL_PATH, sheet_name="Остатки по счетам"))
    except Exception:
        log.exception("Ошибка чтения Excel (accounts)")
        return await update.message.reply_text(
            'Не удалось прочитать лист "Остатки по счетам".'
        )

    # Определяем ключевые столбцы – ищем по известным подстрокам
    cols = {c: idx for idx, c in enumerate(df_acc.columns)}
    bank_col = next((c for c in cols if "банк" in c), None)
    type_col = next((c for c in cols if "тип" in c), None)
    balance_col = next((c for c in cols if "остаток" in c), None)
    if not all([bank_col, type_col, balance_col]):
        return await update.message.reply_text(
            "Не удалось найти столбцы Банк / Тип / Остаток в Excel‑файле."
        )

    header = "Банк              | Тип            | Остаток, ₽"
    lines: list[str] = []
    total_bal = 0.0
    for _, row in df_acc.iterrows():
        bank = str(row[bank_col]).strip()
        acc_type = str(row[type_col]).strip()
        bal = float(row[balance_col] or 0)
        total_bal += bal
        lines.append(f"{bank[:16]:<16} | {acc_type[:12]:<12} | {bal:10.2f}")

    lines.extend(
        (
            "".ljust(len(header), "-"),
            f"ИТОГО             |                | {total_bal:10.2f}",
        )
    )
    await send_plain_table(update, header, lines)


# --- Обработка произвольного сообщения --------------------------
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
    app.add_handler(CommandHandler("categories", categories))
    app.add_handler(CommandHandler("month_plan", month_plan))
    app.add_handler(CommandHandler("accounts", accounts))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("=== Бот запущен ===")
    app.run_polling()


if __name__ == "__main__":
    main()
