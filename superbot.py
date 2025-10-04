"""
Telegram bot for parsing articles from realpython, medium, and stackoverflow.
The bot searches for articles based on user queries, generates short summaries, and caches the results.
"""

import logging
import re
import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
from collections import Counter
from typing import Any

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
from bs4 import BeautifulSoup
from newspaper import Article  # type: ignore
import openai
from openai import OpenAIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== CONFIG ==================
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not API_TOKEN:
    raise ValueError("API_TOKEN not found in .env")

if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_OPENAI_API_KEY_HERE":
    logging.warning("OPENAI_API_KEY not found in .env or is a placeholder. Falling back to basic summarizer.")
    openai.api_key = None
else:
    openai.api_key = OPENAI_API_KEY

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
DB_FILE = "cache.db"

SITES = {
    "realpython": "https://realpython.com/search/?q={}",
    "medium": "https://medium.com/search?q={}",
    "stackoverflow": "https://stackoverflow.com/search?q={}"
}

scheduler = AsyncIOScheduler()

# ================== DATABASE ==================
def init_db() -> None:
    """Initialize the database for caching, user sites, and subscriptions."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            query TEXT,
            response TEXT,
            created_at TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sites (
            user_id INTEGER,
            site_url TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER,
            query TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_cache(query: str, response: str) -> None:
    """Save a response to the cache."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cache VALUES (?, ?, ?)",
        (query, response, datetime.now())
    )
    conn.commit()
    conn.close()

def load_cache(query: str, ttl_minutes: int = 60) -> Any | None:
    """Load a response from the cache if it's still valid."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT response, created_at FROM cache WHERE query = ? ORDER BY created_at DESC LIMIT 1",
        (query,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            saved_time = datetime.strptime(str(row[1]), "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            saved_time = datetime.strptime(str(row[1]), "%Y-%m-%d %H:%M:%S")
        if datetime.now() - saved_time < timedelta(minutes=ttl_minutes):
            return row[0]
    return None

def get_user_sites(user_id: int) -> list[str]:
    """Retrieve the list of sites for a specific user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT site_url FROM user_sites WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        # Add default sites if user has no custom sites
        default_sites = ["https://realpython.com/search/?q=", "https://medium.com/search?q=", "https://stackoverflow.com/search?q="]
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executemany("INSERT INTO user_sites (user_id, site_url) VALUES (?, ?)", [(user_id, site) for site in default_sites])
        conn.commit()
        conn.close()
        return default_sites

    return [row[0] for row in rows]

def add_user_site(user_id: int, site_url: str) -> None:
    """Add a new site to the user's list."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_sites (user_id, site_url) VALUES (?, ?)", (user_id, site_url))
    conn.commit()
    conn.close()

def remove_user_site(user_id: int, site_url: str) -> None:
    """Remove a site from the user's list."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sites WHERE user_id = ? AND site_url = ?", (user_id, site_url))
    conn.commit()
    conn.close()

def reset_user_sites(user_id: int) -> None:
    """Reset the user's site list to default."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sites WHERE user_id = ?", (user_id,))
    default_sites = ["https://realpython.com/search/?q=", "https://medium.com/search?q=", "https://stackoverflow.com/search?q="]
    cursor.executemany("INSERT INTO user_sites (user_id, site_url) VALUES (?, ?)", [(user_id, site) for site in default_sites])
    conn.commit()
    conn.close()

# ================== SUBSCRIPTIONS ==================
# Database functions for subscriptions
def add_subscription(user_id: int, query: str) -> None:
    """Add a subscription for a user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO subscriptions (user_id, query) VALUES (?, ?)", (user_id, query))
    conn.commit()
    conn.close()

def remove_subscription(user_id: int, query: str) -> None:
    """Remove a subscription for a user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE user_id = ? AND query = ?", (user_id, query))
    conn.commit()
    conn.close()

def get_subscriptions(user_id: int) -> list[str]:
    """Get all subscriptions for a user."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT query FROM subscriptions WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

# Command handlers
@dp.message(Command("subscribe"))
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

@dp.message(Command("unsubscribe"))
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

@dp.message(Command("subscriptions"))
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

# Scheduled task
async def check_subscriptions():
    """Check for new articles for all subscriptions."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id, query FROM subscriptions")
    subscriptions = cursor.fetchall()
    conn.close()

    async with aiohttp.ClientSession() as session:
        for user_id, query in subscriptions:
            site_results = await asyncio.gather(*[search_links(site, query, session) for site in SITES])
            all_links = [link for sublist in site_results for link in sublist]

            if all_links:
                message = get_response(user_id, f"🔔 New articles for '{query}':\n", f"🔔 Нові статті за запитом '{query}':\n")
                message += "\n".join(all_links[:5])
                try:
                    await bot.send_message(chat_id=user_id, text=message)
                except Exception as e:
                    logging.error(f"Failed to send message to user {user_id}: {e}")

# Initialize scheduler
scheduler.add_job(check_subscriptions, "interval", hours=24)
scheduler.start()

# ================== PARSING ==================
async def fetch_article(url: str) -> tuple[str | None, str | None]:
    """Parse an article using newspaper3k."""
    loop = asyncio.get_event_loop()
    try:
        article = await loop.run_in_executor(None, lambda: Article(url))
        await loop.run_in_executor(None, article.download)
        await loop.run_in_executor(None, article.parse)
        text = article.text.strip().replace("\n", " ")
        return article.title, text
    except (ValueError, IOError) as e:
        logging.error("Error parsing %s: %s", url, e)
        return None, None

async def search_links(site: str, query: str, session: aiohttp.ClientSession) -> list[str]:
    """Search for links on a site."""
    search_url = SITES[site].format(query.replace(" ", "+"))
    try:
        async with session.get(search_url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            if response.status != 200:
                return []
            text = await response.text()
            soup = BeautifulSoup(text, "html.parser")
            links: list[str] = []

            if site == "realpython":
                results = soup.select(".card-title a")  # type: ignore
                for a in results[:5]:
                    href = a.get("href")
                    if href:
                        links.append("https://realpython.com" + str(href))
            elif site == "medium":
                results = soup.find_all("a", href=re.compile(r"https://medium.com/.*"))  # type: ignore
                unique_links = list(dict.fromkeys([str(a.get("href", "")).split("?")[0] for a in results if a.get("href")]))
                links = unique_links[:5]
            elif site == "stackoverflow":
                results = soup.select(".s-post-summary--content .s-link")  # type: ignore
                for a in results[:5]:
                    href = a.get("href")
                    if href:
                        links.append("https://stackoverflow.com" + str(href))

            return links
    except aiohttp.ClientError as e:
        logging.error("Error searching on %s: %s", site, e)
        return []

# ================== SUMMARY ==================
async def get_ai_summary(texts: list[str], query: str) -> str:
    """Generate a summary using OpenAI's GPT."""
    if not openai.api_key:
        logging.warning("OpenAI API key not set. Falling back to basic summarizer.")
        return summarize_texts(texts)

    full_text = "\n\n".join(texts)
    # Truncate to avoid exceeding token limits
    max_length = 12000  # Roughly 3000 tokens
    if len(full_text) > max_length:
        full_text = full_text[:max_length]

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes texts."},
                    {"role": "user", "content": f"Based on the following articles, provide a concise summary of the key findings regarding '{query}'. The summary should be a single, coherent paragraph of 3-5 sentences. Here is the text:\n\n{full_text}"}
                ],
                temperature=0.5,
                max_tokens=150,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
        )
        if response.choices:
            choice_content = response.choices[0].message.content if response.choices[0].message.content else ""
            return choice_content.strip()
        return "Could not generate an AI summary."
    except (OpenAIError, ValueError, TypeError) as e:
        logging.error("Error calling OpenAI API: %s", e)
        return "Failed to generate AI summary. Falling back to basic method."

def summarize_texts(texts: list[str], max_sentences: int = 3) -> str:
    """Create a short summary based on article texts (basic fallback)."""
    sentences: list[str] = []
    for txt in texts:
        parts = re.split(r'(?<=[.!?]) +', txt)
        sentences.extend(parts)

    if not sentences:
        return "Could not generate a short summary."

    word_freq = Counter(" ".join(sentences).lower().split())
    ranked = sorted(sentences, key=lambda s: sum(word_freq.get(w, 0) for w in s.lower().split()), reverse=True)
    summary = " ".join(ranked[:max_sentences])
    return summary.strip()

# ================== LANGUAGE SUPPORT ==================
user_languages = {}

@dp.message(Command("start", "help"))
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

@dp.callback_query(F.data.startswith("lang:"))
async def set_language(callback_query: types.CallbackQuery):
    """Set the user's preferred language based on their selection."""
    if not callback_query.data:
        await callback_query.answer("No data provided.", show_alert=True)
        return

    lang = callback_query.data.split(":")[1]
    user_languages[callback_query.from_user.id] = lang
    if lang == "en":
        if callback_query.message:
            await callback_query.message.reply("Language set to English.")
    elif lang == "uk":
        if callback_query.message:
            await callback_query.message.reply("Мова змінена на українську.")
    await callback_query.answer()

# Modify responses to use the selected language
def get_response(user_id: int, en_text: str, uk_text: str) -> str:
    """Return the response text in the user's preferred language."""
    lang = user_languages.get(user_id, "en")
    return en_text if lang == "en" else uk_text

# ================== BOT HANDLERS ==================
@dp.message(Command("find"))
async def find_handler(message: types.Message, command: CommandObject) -> None:
    query = command.args
    if not query:
        await message.reply(
            "Please enter a query after the command.\nExample: `/find best python frameworks`"
        )
        return

    cached = load_cache(query)
    if cached:
        await message.reply(cached, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        return

    msg = await message.reply("⏳ Searching for information, please wait...")

    async with aiohttp.ClientSession() as session:
        site_results = await asyncio.gather(*[search_links(site, query, session) for site in SITES])

    # Збираємо посилання по черзі з усіх сайтів
    all_links: list[str] = []
    max_links = 5
    index = 0
    while len(all_links) < max_links:
        added = False
        for site_links in site_results:
            if index < len(site_links):
                all_links.append(site_links[index])
                added = True
                if len(all_links) >= max_links:
                    break
        if not added:
            break
        index += 1

    if not all_links:
        await msg.edit_text("Could not find any articles. Try another topic.")
        return

    article_tasks = [fetch_article(link) for link in all_links]
    articles = await asyncio.gather(*article_tasks)

    ideas: list[str] = []
    texts: list[str] = []
    for (title, text), link in zip(articles, all_links):
        if title and text:
            snippet = " ".join(text.split()[:30])
            ideas.append(f"*{title}*:\n{snippet}... [Read]({link})")
            texts.append(text)

    if not ideas:
        await msg.edit_text("Could not extract content from the pages.")
        return

    summary = await get_ai_summary(texts, query) if openai.api_key else summarize_texts(texts)

    response = f"🔎 *Query:* {query}\n\n"
    response += "🔍 *Key Ideas:*\n" + "\n\n".join(f"- {idea}" for idea in ideas) + "\n\n"
    response += f"✅ *Conclusion:*\n{summary}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 Show all sources", callback_data=f"sources:{query}")],
            [InlineKeyboardButton(text="📋 Copy conclusion", callback_data=f"copy:{query}")]
        ]
    )

    await msg.edit_text(
        text=response,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
        disable_web_page_preview=True
    )

    save_cache(query, response)

@dp.callback_query(F.data.startswith("sources:"))
async def show_sources(callback_query: types.CallbackQuery) -> None:
    msg = callback_query.message
    if not msg or not isinstance(msg, types.Message) or not callback_query.data:
        await callback_query.answer("Message not found or data is missing.", show_alert=True)
        return
    query = callback_query.data.split(":", 1)[1]

    async with aiohttp.ClientSession() as session:
        tasks = [search_links(site, query, session) for site in SITES]
        results = await asyncio.gather(*tasks)
    all_links = [link for sublist in results for link in sublist]

    if not all_links:
        await msg.reply("Could not find sources for this query.")
        await callback_query.answer()
        return

    text = "📄 *Sources:*\n" + "\n".join(f"{i}. {link}" for i, link in enumerate(all_links, 1))
    await msg.reply(text, parse_mode=ParseMode.MARKDOWN)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("copy:"))
async def copy_summary(callback_query: types.CallbackQuery) -> None:
    msg = callback_query.message
    if not msg or not isinstance(msg, types.Message) or not callback_query.data:
        await callback_query.answer("Message not found or data is missing.", show_alert=True)
        return
    query = callback_query.data.split(":", 1)[1]

    cached = load_cache(query)
    if cached:
        summary = str(cached).split("✅ *Conclusion:*", 1)[-1].strip()
        await msg.reply(f"📋 Copied:\n\n```{summary}```", parse_mode=ParseMode.MARKDOWN)
    else:
        await msg.reply("Conclusion not found. The cache might have expired.")
    await callback_query.answer()

@dp.message(Command("addsite"))
async def add_site_handler(message: types.Message, command: CommandObject) -> None:
    """Allow users to add a custom site for parsing."""
    site_url = command.args
    if not site_url:
        await message.reply("Please provide a valid site URL after the command.\nExample: `/addsite https://example.com`")
        return

    if not re.match(r'https?://[\w.-]+', site_url):
        await message.reply("Invalid URL format. Please provide a valid site URL.")
        return

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(site_url) as response:
                if response.status != 200:
                    await message.reply(f"The site `{site_url}` is not reachable (status code: {response.status}). Please check the URL.")
                    return
    except aiohttp.ClientError as e:
        await message.reply(f"Failed to reach the site `{site_url}`. Error: {str(e)}")
        return

    SITES[site_url] = site_url + "?q={}"
    await message.reply(f"The site `{site_url}` has been added successfully! You can now use `/find` to search it.")

# ================== FIXING ERRORS ==================
from aiogram import types, Dispatcher
from aiogram.types import Message

# Fixing the decorator usage
@dp.message(commands=['add_source'])
async def add_source(message: Message):
    """Handle the /add_source command to add a new site."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Не вдалося визначити ваш ідентифікатор користувача.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Пожалуйста, укажите URL сайта после команды. Пример: /add_source https://example.com")
        return

    site_url = args[1].strip()
    add_user_site(user_id, site_url)
    await message.reply(f"Сайт {site_url} успішно додано до вашого списку.")

@dp.message(commands=['my_sources'])
async def my_sources(message: Message):
    """Handle the /my_sources command to list user sites."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Не вдалося визначити ваш ідентифікатор користувача.")
        return

    sites = get_user_sites(user_id)
    if not sites:
        await message.reply("Ваш список сайтів пустий.")
        return

    sites_list = "\n".join(sites)
    await message.reply(f"Ваші сайти:\n{sites_list}")

@dp.message(commands=['remove_source'])
async def remove_source(message: Message):
    """Handle the /remove_source command to remove a site."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Не вдалося визначити ваш ідентифікатор користувача.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Будь ласка, вкажіть URL сайту для видалення. Приклад: /remove_source https://example.com")
        return

    site_url = args[1].strip()
    remove_user_site(user_id, site_url)
    await message.reply(f"Сайт {site_url} успішно видалено з вашого списку.")

@dp.message(commands=['reset_sources'])
async def reset_sources(message: Message):
    """Handle the /reset_sources command to reset user sites to default."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Не вдалося визначити ваш ідентифікатор користувача.")
        return

    reset_user_sites(user_id)
    await message.reply("Ваш список сайтів був скинутий до налаштувань за замовчуванням.")

# ================== RUN ==================
async def main() -> None:
    """Start the bot."""
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
