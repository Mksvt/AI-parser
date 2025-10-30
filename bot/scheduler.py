"""Scheduler for periodic tasks"""
import logging
import asyncio
import sqlite3

import aiohttp
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

from .config import DB_FILE, SITES
from .parsing import search_links
from .localization import get_response

scheduler = AsyncIOScheduler()

async def check_subscriptions(bot: Bot):
    """Check for new articles for all subscriptions."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id, query FROM subscriptions")
    subscriptions = cursor.fetchall()
    conn.close()

    async with aiohttp.ClientSession() as session:
        for user_id, query in subscriptions:
            # Use get_user_sites to get the list of sites for the user
            # For now, using the global SITES
            site_results = await asyncio.gather(*[search_links(site, query, session) for site in SITES])
            all_links = [link for sublist in site_results for link in sublist]

            if all_links:
                message_text = get_response(user_id, f"🔔 New articles for '{query}':\n", f"🔔 Нові статті за запитом '{query}':\n")
                message_text += "\n".join(all_links[:5])
                try:
                    await bot.send_message(chat_id=user_id, text=message_text)
                except Exception as e:
                    logging.error("Failed to send message to user %s: %s", user_id, e)

def setup_scheduler(bot: Bot):
    """Add the subscription check job to the scheduler."""
    scheduler.add_job(check_subscriptions, "interval", hours=24, args=(bot,))
    scheduler.start()
