from aiogram import types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import add_subscription, remove_subscription, get_subscriptions
from .localization import get_response

async def subscribe_handler(message: types.Message, command: CommandObject):
    """Handle the /subscribe command to add a subscription."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Не удалось определить ваш идентификатор пользователя.")
        return

    query = command.args
    if not query:
        await message.reply(get_response(user_id, "Please provide a query to subscribe. Example: /subscribe Python", "Будь ласка, вкажіть запит для підписки. Наприклад: /subscribe Python"))
        return

    add_subscription(user_id, query)
    await message.reply(get_response(user_id, f"You have successfully subscribed to: {query}", f"Ви успішно підписалися на запит: {query}"))

async def unsubscribe_handler(message: types.Message, command: CommandObject):
    """Handle the /unsubscribe command to remove a subscription."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Не удалось определить ваш идентификатор пользователя.")
        return

    query = command.args
    if not query:
        await message.reply(get_response(user_id, "Please provide a query to unsubscribe. Example: /unsubscribe Python", "Будь ласка, вкажіть запит для відписки. Наприклад: /unsubscribe Python"))
        return

    remove_subscription(user_id, query)
    await message.reply(get_response(user_id, f"You have successfully unsubscribed from: {query}", f"Ви успішно відписалися від запиту: {query}"))

async def subscriptions_handler(message: types.Message):
    """Handle the /subscriptions command to list all subscriptions."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Не удалось определить ваш идентификатор пользователя.")
        return

    subscriptions = get_subscriptions(user_id)
    if not subscriptions:
        await message.reply(get_response(user_id, "You have no active subscriptions.", "У вас немає активних підписок."))
        return

    subscriptions_list = "\n".join(subscriptions)
    await message.reply(get_response(user_id, f"Your subscriptions:\n{subscriptions_list}", f"Ваші підписки:\n{subscriptions_list}"))