import os

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # ИИ настройки
    USE_AI: bool = os.getenv("USE_AI", "false").lower() == "true"
    GEMINI_PROXY_URL: str = os.getenv("GEMINI_PROXY_URL", "")  # Cloudflare Worker URL для обхода блокировки в РФ
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # YandexGPT (альтернатива для РФ)
    YANDEX_API_KEY: str = os.getenv("YANDEX_API_KEY", "")
    YANDEX_FOLDER_ID: str = os.getenv("YANDEX_FOLDER_ID", "")
    YANDEX_MODEL: str = os.getenv("YANDEX_MODEL", "yandexgpt-lite")

    category_ids_str = os.getenv("KWORK_CATEGORY_IDS", "")
    category_ids = [int(cat.strip()) for cat in category_ids_str.split(",") if cat.strip()]
    KWORK_CATEGORY_IDS: list[int] = category_ids

    KEYWORDS: list[str] = []

    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "60"))

    MAX_REPLIES: int = int(os.getenv("MAX_REPLIES", "15"))
    MAX_AGE_HOURS: float = float(os.getenv("MAX_AGE_HOURS", "2.0"))

    PAGE_LOAD_TIMEOUT: int = int(os.getenv("PAGE_LOAD_TIMEOUT", "30000"))

    SEEN_ORDERS_FILE: str = os.getenv("SEEN_ORDERS_FILE", "/data/seen_orders.json")

    SEEN_ORDER_TTL_HOURS: int = int(os.getenv("SEEN_ORDER_TTL_HOURS", "24"))

    MAX_ORDERS_PER_CATEGORY: int = int(os.getenv("MAX_ORDERS_PER_CATEGORY", "5"))

    MAX_ORDERS_PER_CYCLE: int = int(os.getenv("MAX_ORDERS_PER_CYCLE", "20"))

    MAX_SEEN_ORDERS: int = int(os.getenv("MAX_SEEN_ORDERS", "500"))
    SEEN_ORDER_MAX_AGE_DAYS: int = int(os.getenv("SEEN_ORDER_MAX_AGE_DAYS", "7"))


settings = Settings()