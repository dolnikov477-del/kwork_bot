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
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")

    # Категории Kwork
    category_ids_str = os.getenv("KWORK_CATEGORY_IDS", "")
    category_ids = [int(cat.strip()) for cat in category_ids_str.split(",") if cat.strip()]
    KWORK_CATEGORY_IDS: list[int] = category_ids

    # НЕ фильтруем по ключевым словам.
    # Парсим только выбранные категории.
    KEYWORDS: list[str] = []

    # Интервал проверки
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "90"))

    # Фильтр старых/запаленных заказов
    MAX_REPLIES: int = int(os.getenv("MAX_REPLIES", "6"))
    MAX_AGE_HOURS: int = int(os.getenv("MAX_AGE_HOURS", "2"))

    # Файл с просмотренными заказами (для Railway Volume используйте /data/seen_orders.json)
    SEEN_ORDERS_FILE: str = os.getenv("SEEN_ORDERS_FILE", "/data/seen_orders.json")


settings = Settings()