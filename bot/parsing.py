import logging
import re
import asyncio

import aiohttp
from bs4 import BeautifulSoup
from newspaper import Article  # type: ignore

from .config import SITES

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
