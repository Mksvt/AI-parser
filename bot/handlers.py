from aiogram import types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .database import add_subscription, remove_subscription, get_subscriptions
from .localization import get_response, user_languages

async def start_handler(message: types.Message):
    """Handle the /start and /help commands to display a welcome message and language options."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="English", callback_data="lang:en"),
             InlineKeyboardButton(text="Українська", callback_data="lang:uk")]
        ]
    )
    await message.reply(
        "Hi! I'm a parser bot. Please select your language:",
        reply_markup=keyboard
    )

async def set_language(callback_query: types.CallbackQuery):
    """Set the user's preferred language based on their selection."""
    if not callback_query.data:
        await callback_query.answer("No data provided.", show_alert=True)
        return

    lang = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    user_languages[user_id] = lang
    
    response_text = ""
    if lang == "en":
        response_text = "Language set to English."
    elif lang == "uk":
        response_text = "Мову змінено на українську."
    
    if callback_query.message and isinstance(callback_query.message, types.Message):
        try:
            # Edit the original message to show the choice and remove the buttons
            await callback_query.message.edit_text(
                f"{callback_query.message.text}\n\n_{response_text}_",
                reply_markup=None 
            )
        except Exception:
            # If editing fails, just send a new message
            await callback_query.message.answer(response_text)

    await callback_query.answer()

async def subscribe_handler(message: types.Message, command: CommandObject):
    """Handle the /subscribe command to add a subscription."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Не вдалося визначити ваш ідентифікатор користувача.")
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
        await message.reply("Не вдалося визначити ваш ідентифікатор користувача.")
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
        await message.reply("Не вдалося визначити ваш ідентифікатор користувача.")
        return

    subscriptions = get_subscriptions(user_id)
    if not subscriptions:
        await message.reply(get_response(user_id, "You have no active subscriptions.", "У вас немає активних підписок."))
        return

    subscriptions_list = "\n".join(subscriptions)
    await message.reply(get_response(user_id, f"Your subscriptions:\n{subscriptions_list}", f"Ваші підписки:\n{subscriptions_list}"))
