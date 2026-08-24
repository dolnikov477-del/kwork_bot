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
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-70b-8192")

    # Категории Kwork
    category_ids_str = os.getenv("KWORK_CATEGORY_IDS", "")
    category_ids = [int(cat.strip()) for cat in category_ids_str.split(",") if cat.strip()]
    KWORK_CATEGORY_IDS: list[int] = category_ids

    # НЕ фильтруем по ключевым словам.
    # Парсим только выбранные категории.
    KEYWORDS: list[str] = []

    # Интервал проверки
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "300"))

    # Фильтр старых/запаленных заказов
    MAX_REPLIES: int = int(os.getenv("MAX_REPLIES", "6"))
    MAX_AGE_HOURS: int = int(os.getenv("MAX_AGE_HOURS", "2"))

    # Таймаут загрузки страницы в парсере (миллисекунды)
    PAGE_LOAD_TIMEOUT: int = int(os.getenv("PAGE_LOAD_TIMEOUT", "30000"))

    # Файл с просмотренными заказами (для Railway Volume используйте /data/seen_orders.json)
    SEEN_ORDERS_FILE: str = os.getenv("SEEN_ORDERS_FILE", "/data/seen_orders.json")

    # Через сколько часов забываем, что уже видели заказ
    SEEN_ORDER_TTL_HOURS: int = int(os.getenv("SEEN_ORDER_TTL_HOURS", "6"))

    # Максимум заказов из одной категории за один цикл
    MAX_ORDERS_PER_CATEGORY: int = int(os.getenv("MAX_ORDERS_PER_CATEGORY", "3"))

    # Ограничения для файла просмотренных заказов
    MAX_SEEN_ORDERS: int = int(os.getenv("MAX_SEEN_ORDERS", "500"))
    SEEN_ORDER_MAX_AGE_DAYS: int = int(os.getenv("SEEN_ORDER_MAX_AGE_DAYS", "7"))


settings = Settings()