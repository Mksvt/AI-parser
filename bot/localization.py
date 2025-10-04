user_languages = {}

def get_response(user_id: int, en_text: str, uk_text: str) -> str:
    """Return the response text in the user's preferred language."""
    lang = user_languages.get(user_id, "en")
    return en_text if lang == "en" else uk_text