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

    # Модели Gemini в порядке приоритета (fallback chain)
    GEMINI_MODELS: list[str] = _split_csv(os.getenv("GEMINI_MODELS", "gemini-3.8-flash,gemini-2.5-flash,gemini-2.5-flash-lite"))

    # Ретраи и параллелизм
    MAX_ATTEMPTS_PER_MODEL: int = int(os.getenv("MAX_ATTEMPTS_PER_MODEL", "5"))
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "2"))
    REQUEST_START_DELAY: float = float(os.getenv("REQUEST_START_DELAY", "0.5"))

    # Системный шаблон отклика (fallback) — минимум 400 символов
    FALLBACK_TEMPLATE: str = os.getenv(
        "FALLBACK_TEMPLATE",
        "Здравствуйте! Меня зовут Артём. Внимательно изучил ваш заказ «{title}» и понял, какая задача стоит перед нами. Имею релевантный опыт решения подобных задач: разрабатывал телеграм-ботов, парсеров, автоматизировал бизнес-процессы, делал интеграции с CRM и маркетплейсами. Знаю типичные подводные камни и как их обойти, чтобы результат получился стабильным и в срок. Готов взяться за работу сразу после уточнения деталей — напишите, пожалуйста, что именно важно в вашем случае, и я назову точные сроки и стоимость. Жду вашего ответа, чтобы начать!"
    )

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