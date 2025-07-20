"""
Telegram personal finance tracker bot

Command list:
/start       – greeting and brief instructions
/categories  – show category limits vs spent for the current (bank) month
/tracker     – show the expense register **as a table** for a chosen period
               (defaults to *current week*, Mon‑Sun)

Add an expense by sending a message in the format:
Категория, сумма, комментарий
Example:  Продукты, 1170, Пятёрочка

Only users from ALLOWED_USERS in config.ini may interact with the bot.

2025‑06‑05  ▸ NEW  /tracker now prints a monospace table of every expense in the
               selected period (inclusive) and, if no dates are supplied, shows
               the current calendar week.  Accepts optional arguments
               DD.MM.YYYY DD.MM.YYYY.
             ▸ FIX  /categories sheet detection remains the same but with extra
               logging.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import shorten

import pandas as pd
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import configparser

# -----------------------------------------------------------
# Logging configuration
# -----------------------------------------------------------
logging.basicConfig(
    filename="tracker.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s → %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("fin_tracker")

# -----------------------------------------------------------
# Configuration
# -----------------------------------------------------------
config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

EXCEL_PATH = Path(config.get("bot", "EXCEL_PATH", fallback=r"Финансовый_план_и_долги (8).xlsx"))

ALLOWED_USERS: list[int] = [
    int(uid) for uid in config.get("bot", "ALLOWED_USERS", fallback="").split(",") if uid.strip()
]

LIMIT_COLS = {"Категория", "Примерная сумма в месяц (₽)"}

# -----------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------

def is_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


def current_week_bounds() -> tuple[datetime, datetime]:
    """Return start (Mon 00:00) and end (next Mon 00:00) for *current* calendar week."""
    today = datetime.today()
    start = today - timedelta(days=today.weekday())  # Monday
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end


def period_bounds_month() -> tuple[datetime, datetime]:
    """Accounting month 4‑th → next 4‑th (used by /categories)."""
    today = datetime.today()
    start = datetime(today.year, today.month, 4)
    if today.day < 4:
        start -= timedelta(days=30)
        start = start.replace(day=4)
    end_tmp = start + timedelta(days=31)
    end = datetime(end_tmp.year, end_tmp.month, 4)
    return start, end


def load_tracker(parse_dates: bool = True) -> pd.DataFrame:
    return pd.read_excel(
        EXCEL_PATH,
        sheet_name="Трекер расходов",
        parse_dates=["Дата"] if parse_dates else None,
    )


def load_limits() -> pd.DataFrame:
    xls = pd.ExcelFile(EXCEL_PATH)
    for name in xls.sheet_names:
        if "трекер" in name.lower():
            continue
        try:
            df = pd.read_excel(xls, sheet_name=name)
        except Exception as exc:
            logger.warning("Cannot read sheet %s: %s", name, exc)
            continue
        if LIMIT_COLS.issubset(df.columns):
            logger.debug("Using limits sheet: %s", name)
            return df
    logger.warning("No limits sheet found – using first sheet as fallback")
    return pd.read_excel(xls, sheet_name=xls.sheet_names[0])


def format_table(header: list[str], rows: list[list[str]]) -> str:
    """Return a monospace table wrapped in <pre>…</pre>."""
    # compute column widths
    widths = [len(h) for h in header]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))
    # build lines
    def fmt_row(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [fmt_row(header), "-" * (sum(widths) + 3 * (len(widths) - 1))]
    lines += [fmt_row(r) for r in rows]
    return "<pre>" + "\n".join(lines) + "</pre>"

# -----------------------------------------------------------
# Bot command handlers
# -----------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")

    await update.message.reply_text(
        "Привет! Отправь расход: Категория, сумма, комментарий.\n\n"
        "Команды:\n"
        "/categories – лимиты за текущий *учётный* месяц;\n"
        "/tracker    – список расходов за период (по умолчанию – текущая неделя)."
    )


async def categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")
    try:
        df_limits = load_limits()
    except Exception as exc:
        logger.exception("limits read failed: %s", exc)
        return await update.message.reply_text("Не удалось прочитать лимиты расходов.")

    df_tr = load_tracker()
    start_date, end_date = period_bounds_month()
    df_period = df_tr[(df_tr["Дата"] >= start_date) & (df_tr["Дата"] < end_date) & (df_tr["Учитывается в анализе?"] == "Да")]

    header = ["Категория", "Лимит", "Потрачено", "Остаток"]
    rows: list[list[str]] = []
    for _, row in df_limits.iterrows():
        cat = str(row.get("Категория", "")).strip()
        if not cat:
            continue
        limit = float(row.get("Примерная сумма в месяц (₽)", 0) or 0)
        spent = float(df_period[df_period["Категория"] == cat]["Сумма (₽)"].sum())
        remain = limit - spent
        rows.append([cat, f"{limit:.0f}", f"{spent:.0f}", f"{remain:.0f}"])

    table = format_table(header, rows)
    period_txt = f"{start_date.strftime('%d.%m')}–{(end_date - timedelta(days=1)).strftime('%d.%m')}"
    await update.message.reply_text(f"\U0001F4C8 Категории расходов ({period_txt})\n" + table, parse_mode=constants.ParseMode.HTML)


async def tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tracker [DD.MM.YYYY DD.MM.YYYY] – list expenses as table"""
    if not is_authorized(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    args = context.args
    if len(args) == 2:
        try:
            start_date = datetime.strptime(args[0], "%d.%m.%Y")
            end_date = datetime.strptime(args[1], "%d.%m.%Y") + timedelta(days=1)
        except ValueError:
            return await update.message.reply_text("Формат: /tracker DD.MM.YYYY DD.MM.YYYY")
    elif len(args) == 0:
        start_date, end_date = current_week_bounds()
    else:
        return await update.message.reply_text("Нужно 0 или 2 даты. Пример: /tracker 01.05.2025 07.05.2025")

    df = load_tracker()
    period_df = df[(df["Дата"] >= start_date) & (df["Дата"] < end_date) & (df["Учитывается в анализе?"] == "Да")]

    if period_df.empty:
        return await update.message.reply_text("За указанный период расходов нет ✨")

    header = ["Дата", "Категория", "Сумма", "Комментарий"]
    rows: list[list[str]] = []
    rows.extend(
        [
            r["Дата"].strftime("%d.%m"),
            shorten(str(r["Категория"]), width=14, placeholder="…"),
            f"{r['Сумма (₽)']:.0f}",
            shorten(str(r.get("Комментарий", "")), width=20, placeholder="…"),
        ]
        for _, r in period_df.sort_values("Дата").iterrows()
    )
    table = format_table(header, rows)
    period_txt = f"{start_date.strftime('%d.%m.%Y')}–{(end_date - timedelta(days=1)).strftime('%d.%m.%Y')}"
    await update.message.reply_text(f"\U0001F4C3 Расходы {period_txt}\n" + table, parse_mode=constants.ParseMode.HTML)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return await update.message.reply_text("⛔ Нет доступа.")

    text = update.message.text.strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return await update.message.reply_text("Формат: Категория, сумма, комментарий")

    category, amount_raw, *comment_parts = parts
    try:
        amount = float(amount_raw.replace("₽", "").replace(" ", ""))
    except ValueError:
        return await update.message.reply_text("Сумма должна быть числом")

    comment = ", ".join(comment_parts)

    try:
        df = load_tracker(parse_dates=False)
        new_row = pd.DataFrame(
            {
                "Дата": [datetime.now().date()],
                "Категория": [category],
                "Сумма (₽)": [amount],
                "Комментарий": [comment],
                "Учитывается в анализе?": ["Да"],
            }
        )
        df = pd.concat([df, new_row], ignore_index=True)
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
            df.to_excel(w, sheet_name="Трекер расходов", index=False)
    except Exception as exc:
        logger.exception("Excel write error: %s", exc)
        return await update.message.reply_text("Не удалось записать расход.")

    logger.info("Add expense: %s %.2f %s", category, amount, comment)
    await update.message.reply_text(f"✅ Записано: {category}, {amount:.0f}₽{', '+comment if comment else ''}")


# -----------------------------------------------------------
# Entry point
# -----------------------------------------------------------

def main() -> None:
    application = ApplicationBuilder().token(config["bot"]["TOKEN"]).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("categories", categories))
    application.add_handler(CommandHandler("tracker", tracker))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started – polling…")
    application.run_polling()


if __name__ == "__main__":
    main()
