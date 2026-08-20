import os

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    # Токен Telegram-бота
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Chat ID
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Категории Kwork
    category_ids_str = os.getenv("KWORK_CATEGORY_IDS", "")
    category_ids = [int(cat.strip()) for cat in category_ids_str.split(",") if cat.strip()]
    KWORK_CATEGORY_IDS: list[int] = category_ids

    # НЕ фильтруем по ключевым словам.
    # Парсим только выбранные категории.
    KEYWORDS: list[str] = []

    # Интервал проверки
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "90"))

    # База уже просмотренных заказов
    DB_PATH: str = os.getenv("DB_PATH", "seen_orders.db")


settings = Settings()