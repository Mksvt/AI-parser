import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_FILE = "cache.db"

if not API_TOKEN:
    raise ValueError("API_TOKEN not found in .env")

if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_OPENAI_API_KEY_HERE":
    OPENAI_API_KEY = None