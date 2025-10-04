import logging
import asyncio
from aiogram import Bot, Dispatcher
from bot.config import API_TOKEN
from bot.database import init_db
from bot.handlers import subscribe_handler, unsubscribe_handler, subscriptions_handler
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Register handlers
dp.message.register(subscribe_handler, Command("subscribe"))
dp.message.register(unsubscribe_handler, Command("unsubscribe"))
dp.message.register(subscriptions_handler, Command("subscriptions"))

async def main() -> None:
    """Start the bot."""
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())