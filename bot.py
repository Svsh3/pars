import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from wb_scraper import process_queries
from excel_builder import save_to_excel

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TELEGRAM_TOKEN_HERE")
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "wb2024")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class AuthStates(StatesGroup):
    waiting_password = State()
    authorized = State()


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(AuthStates.waiting_password)
    await message.answer(
        "👋 Привет! Это WB Parser Bot.\n\n"
        "🔐 Введите пароль для доступа:"
    )


@dp.message(AuthStates.waiting_password)
async def check_password(message: Message, state: FSMContext):
    if message.text == BOT_PASSWORD:
        await state.set_state(AuthStates.authorized)
        await message.answer(
            "✅ Доступ открыт!\n\n"
            "📄 Отправь TXT файл со списком:\n"
            "• поисковых запросов (каждый на новой строке)\n"
            "• ссылок поиска WB (wildberries.ru/...?search=...)\n"
            "• прямых ссылок на товары WB\n\n"
            "Пример содержимого файла:\n"
            "<code>беспроводные наушники\n"
            "https://www.wildberries.ru/catalog/0/search.aspx?search=айфон\n"
            "https://www.wildberries.ru/catalog/123456789/detail.aspx</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Неверный пароль. Попробуйте ещё раз:")


@dp.message(AuthStates.authorized, F.document)
async def handle_document(message: Message, state: FSMContext):
    doc = message.document

    if not doc.file_name.endswith(".txt"):
        await message.answer("⚠️ Нужен файл с расширением .txt")
        return

    status_msg = await message.answer("📥 Скачиваю файл...")

    tg_file = await bot.get_file(doc.file_id)
    raw = await bot.download_file(tg_file.file_path)
    content = raw.read().decode("utf-8")

    lines = [x.strip() for x in content.splitlines() if x.strip()]

    if not lines:
        await status_msg.edit_text("⚠️ Файл пустой.")
        return

    await status_msg.edit_text(
        f"📋 Получено строк: <b>{len(lines)}</b>\n"
        f"⏳ Запускаю парсинг...",
        parse_mode="HTML"
    )

    results = await process_queries(lines)

    if not results:
        await status_msg.edit_text("😔 Не удалось получить данные. Проверьте запросы и попробуйте снова.")
        return

    out_file = f"/tmp/wb_result_{message.from_user.id}.xlsx"
    save_to_excel(results, out_file)

    await status_msg.edit_text(
        f"✅ Готово! Найдено товаров: <b>{len(results)}</b>",
        parse_mode="HTML"
    )
    await message.answer_document(
        FSInputFile(out_file, filename="wb_results.xlsx"),
        caption="📊 Результаты парсинга Wildberries"
    )


@dp.message(AuthStates.authorized)
async def authorized_text(message: Message):
    await message.answer("📄 Отправь TXT файл для парсинга.")


@dp.message()
async def unauthorized(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await state.set_state(AuthStates.waiting_password)
        await message.answer("🔐 Введите пароль для доступа:")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
