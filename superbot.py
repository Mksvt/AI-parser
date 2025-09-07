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

# ================== DATABASE ==================
def init_db() -> None:
    """Initialize the database for caching."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            query TEXT,
            response TEXT,
            created_at TIMESTAMP
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

# ================== RUN ==================
async def main() -> None:
    """Start the bot."""
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
