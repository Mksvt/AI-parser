import sqlite3
from datetime import datetime, timedelta
from typing import Any

DB_FILE = "cache.db"

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