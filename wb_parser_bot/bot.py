#!/usr/bin/env python3
"""
WB Parser Bot — парсер Wildberries через Telegram
"""

import asyncio
import io
import os
import logging
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

from excel_builder import build_pivot_excel
from wb_scraper import search_wb   # ← новый умный парсер

# ── Настройки ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА")
PASSWORD  = "qw1"
TOP_N     = 5

WAIT_PASS = 1
READY     = 2

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Клавиатуры ────────────────────────────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Загрузить запросы (.txt)", callback_data="upload")],
        [InlineKeyboardButton("ℹ️ Как пользоваться",        callback_data="help")],
    ])

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Главное меню", callback_data="menu")],
    ])

# ── Тексты ────────────────────────────────────────────────────────────────────
WELCOME = (
    "🛍️ *WB Parser Bot*\n\n"
    "Привет\\! Я парсю товары с Wildberries и формирую сводную таблицу Excel\\.\n\n"
    "🔐 Введи пароль для доступа:"
)

MAIN_MENU = (
    "✅ *Доступ получен\\!*\n\n"
    "Отправь мне `.txt` файл со списком поисковых запросов "
    "\\(каждый запрос с новой строки\\)\\.\n\n"
    "Я найду топ\\-5 товаров по каждому запросу и верну тебе "
    "готовый Excel с ценами\\."
)

HELP_TEXT = (
    "📖 *Инструкция*\n\n"
    "1\\. Создай файл `queries\\.txt`\n"
    "2\\. Напиши каждый товар с новой строки:\n"
    "```\nбеспроводные наушники\nмеханическая клавиатура\nумные часы\n```\n"
    "3\\. Отправь файл боту\n"
    "4\\. Получи Excel\\-таблицу:\n"
    "   • Строки — названия товаров\n"
    "   • Колонки — продавцы\n"
    "   • Ячейки — цены\n\n"
    "⏱ Обработка \\~1\\-2 сек на запрос"
)

# ── Хендлеры ──────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN_V2)
    return WAIT_PASS

async def check_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == PASSWORD:
        ctx.user_data["auth"] = True
        await update.message.reply_text(
            MAIN_MENU, parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_keyboard()
        )
        return READY
    else:
        await update.message.reply_text(
            "❌ Неверный пароль\\.\nПопробуй ещё раз:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAIT_PASS

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "menu":
        await q.edit_message_text(MAIN_MENU, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_keyboard())
    elif q.data == "upload":
        await q.edit_message_text(
            "📤 *Отправь `.txt` файл с запросами*\n\nКаждый поисковый запрос — с новой строки\\.",
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=back_keyboard()
        )
    elif q.data == "help":
        await q.edit_message_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=back_keyboard())

async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("auth"):
        await update.message.reply_text("🔐 Сначала введи пароль. Напиши /start")
        return WAIT_PASS

    doc = update.message.document
    if not doc or not doc.file_name.endswith(".txt"):
        await update.message.reply_text(
            "⚠️ Отправь именно `.txt` файл с запросами\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return READY

    tg_file = await doc.get_file()
    raw     = await tg_file.download_as_bytearray()
    queries = [l.strip() for l in raw.decode("utf-8").splitlines() if l.strip()]

    if not queries:
        await update.message.reply_text("❌ Файл пустой\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return READY

    if len(queries) > 50:
        await update.message.reply_text(
            "⚠️ Максимум 50 запросов\\. Обрезаю до 50\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        queries = queries[:50]

    total = len(queries)
    progress_msg = await update.message.reply_text(
        f"⏳ *Парсим WB...*\n\n▰▱▱▱▱▱▱▱▱▱ 0/{total}\n\n"
        f"_Прогрев сессии..._",
        parse_mode=ParseMode.MARKDOWN
    )

    all_rows = []
    for i, query in enumerate(queries, 1):
        # Запускаем поиск в отдельном потоке чтобы не блокировать бота
        rows = await asyncio.get_event_loop().run_in_executor(
            None, lambda q=query: search_wb(q, TOP_N)
        )
        all_rows.extend(rows)

        filled = int(i / total * 10)
        bar    = "▰" * filled + "▱" * (10 - filled)
        status = "✅ Готово!" if i == total else f"🔍 `{query}`"
        try:
            await progress_msg.edit_text(
                f"⏳ *Парсим WB...*\n\n{bar} {i}/{total}\n└ {status}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass

    if not all_rows:
        await progress_msg.edit_text("❌ Ничего не найдено\\. Попробуй другие запросы\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return READY

    await progress_msg.edit_text("📊 *Формирую Excel таблицу...*", parse_mode=ParseMode.MARKDOWN)

    xlsx_bytes = build_pivot_excel(all_rows)
    filename   = f"wb_results_{datetime.now().strftime('%d%m%Y_%H%M')}.xlsx"

    caption = (
        f"✅ *Готово\\!*\n\n"
        f"📦 Товаров найдено: *{len(all_rows)}*\n"
        f"🔍 Запросов: *{total}*\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    await update.message.reply_document(
        document=io.BytesIO(xlsx_bytes),
        filename=filename,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_keyboard()
    )
    await progress_msg.delete()
    return READY

# ── Запуск ────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            READY:     [
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.Document.ALL, handle_file),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    log.info("🤖 Bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
