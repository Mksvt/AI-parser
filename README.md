# Telegram Article Parser Bot

This is a multi-functional Telegram bot designed to search for articles on various websites, create short summaries using AI, and manage subscriptions for updates on keywords.

## Core Features

- **Article Search**: Search for articles on sites like Real Python, Medium, Stack Overflow, and more.
- **AI Summaries**: The bot uses OpenAI's GPT to create short and informative summaries of the articles found.
- **Multi-language Support**: Supports both English and Ukrainian languages.
- **Source Management**: Users can add, remove, and view their own list of sites for searching.
- **Subscriptions**: Create subscriptions for keywords, and the bot will send you new articles matching your queries daily.
- **Caching**: Search results are cached to reduce wait times and load.

## How It Works

The bot is built on an asynchronous architecture using `aiogram` to interact with the Telegram API.

1.  **Command Handling**: `main.py` initializes the dispatcher and registers handlers from `bot/handlers.py`. Each command (e.g., `/find` or `/subscribe`) has its own asynchronous handler function.
2.  **Parsing**: When the `/find` command is executed, the bot asynchronously sends requests to the specified sites using `aiohttp`. The HTML pages are parsed with `BeautifulSoup` to extract article links. Then, the `newspaper3k` library is used to download and extract the main text and titles of the articles.
3.  **Summary Generation**: The collected text is sent to the OpenAI API (using the `gpt-3.5-turbo` model). A specially crafted prompt asks the model to create a concise summary based on the provided content.
4.  **Database**: SQLite is used to store:
    - **Cache**: Saves search results for quick access on repeated queries.
    - **Subscriptions**: Stores information about user subscriptions.
    - **User Sources**: Saves custom lists of sites for each user.
5.  **Scheduler**: `apscheduler` is used to run a daily job that checks for new articles for all active user subscriptions and sends them notifications.

## Project Structure

The project has a modular architecture for better organization and scalability:

```
telegram-parser/
├── bot/
│   ├── __init__.py
│   ├── config.py         # Configuration (tokens, settings)
│   ├── database.py       # Database operations (SQLite)
│   ├── handlers.py       # Command and message handlers
│   ├── localization.py   # Language support functions
│   ├── parsing.py        # Website parsing logic
│   ├── scheduler.py      # Scheduler for periodic tasks
│   └── summary.py        # AI-powered summary generation
├── .env                  # File for storing environment variables
├── main.py               # Entry point, bot initialization, and startup
└── README.md             # This file
```

## Installation and Setup

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/Mksvt/AI-parser.git
    cd AI-parser
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    venv\Scripts\activate  # For Windows
    # source venv/bin/activate  # For macOS/Linux
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**
    Create a `.env` file in the project's root directory and add your tokens:

    ```
    API_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
    ```

5.  **Run the bot:**
    ```bash
    python main.py
    ```

## Available Commands

- `/start`, `/help` - Start the bot and select a language.
- `/find <query>` - Search for articles by keyword.
- `/subscribe <query>` - Subscribe to daily updates for a keyword.
- `/unsubscribe <query>` - Unsubscribe from updates.
- `/subscriptions` - View your list of active subscriptions.
- `/add_source <URL>` - Add a site to your personal list of sources.
- `/my_sources` - View your list of sources.
- `/remove_source <URL>` - Remove a site from your list.
- `/reset_sources` - Reset your source list to the default settings.

## Future Plans

- **Upgrade to GPT-4**: Update the model for even higher quality and more accurate summaries.
- **Query Analytics**: Add functionality to analyze popular topics and trends based on user queries.
- **Docker Containerization**: Create a `Dockerfile` to simplify deployment and ensure a consistent environment.
- **Test Coverage**: Write unit tests for key components (parsing, database operations) to improve code reliability.
- **Expanded Site Support**: Add configurations for parsing more popular resources.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
