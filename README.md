# Telegram Parser Bot

## Overview

The Telegram Parser Bot is a powerful tool designed to search for articles on popular platforms like Real Python, Medium, and Stack Overflow. It generates concise summaries of the articles and provides users with key insights directly in Telegram. The bot is built with Python and leverages the OpenAI API for AI-powered summaries.

## Features

- **Search Articles**: Query articles from Real Python, Medium, and Stack Overflow.
- **AI-Powered Summaries**: Generate high-quality summaries using OpenAI's GPT-3.5-turbo.
- **Caching**: Store recent query results in an SQLite database to improve performance.
- **Interactive UI**: Use inline buttons to view sources or copy summaries.
- **Asynchronous Operations**: Fast and efficient article fetching using `aiohttp`.

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Mksvt/AI-parser.git
   cd AI-parser
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   source .venv/bin/activate  # On macOS/Linux
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory and add the following:

   ```env
   API_TOKEN="YOUR_TELEGRAM_BOT_API_TOKEN"
   OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
   ```

5. Run the bot:
   ```bash
   python superbot.py
   ```

## Usage

- Start the bot in Telegram and use the `/start` command to see the welcome message.
- Use the `/find` command followed by your query to search for articles.
  Example: `/find best python frameworks`
- Use the inline buttons to view sources or copy the summary.

## Future Plans

- **Enhanced AI Models**: Upgrade to GPT-4 or other advanced models for even better summaries.
- **Multi-Language Support**: Add support for summarizing articles in multiple languages.
- **Custom Sources**: Allow users to add their own websites for parsing.
- **Advanced Analytics**: Provide insights like article popularity or trends based on user queries.
- **Improved Caching**: Implement a more robust caching mechanism with expiration policies.

## Contributing

Contributions are welcome! Feel free to fork the repository and submit pull requests.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

---

_Happy Parsing!_
