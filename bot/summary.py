import logging
import re
import asyncio
from collections import Counter

import openai
from openai import OpenAIError

from .config import OPENAI_API_KEY

# Initialize OpenAI
if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_OPENAI_API_KEY_HERE":
    logging.warning("OPENAI_API_KEY not found in .env or is a placeholder. Falling back to basic summarizer.")
    openai.api_key = None
else:
    openai.api_key = OPENAI_API_KEY

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
        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
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
