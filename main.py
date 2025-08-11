import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from database import db
from handlers import main_handler

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()
    dp.include_router(main_handler.router)
    await db.init_db()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await db.close_db()

if __name__ == '__main__':
    asyncio.run(main())
