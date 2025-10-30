import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from bot.config import API_TOKEN
from bot.database import init_db
from bot.handlers import (
    subscribe_handler, unsubscribe_handler, subscriptions_handler,
    start_handler, set_language
)
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

if not API_TOKEN:
    raise ValueError("API_TOKEN is not set in the environment variables.")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Register handlers
dp.message.register(start_handler, Command("start", "help"))
dp.callback_query.register(set_language, F.data.startswith("lang:"))
dp.message.register(subscribe_handler, Command("subscribe"))
dp.message.register(unsubscribe_handler, Command("unsubscribe"))
dp.message.register(subscriptions_handler, Command("subscriptions"))

async def main() -> None:
    """Start the bot."""
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())