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

# Системный шаблон отклика (fallback) — один оптимальный, ~400+ символов
    # Подстановки: {title}, {action} (ключевое действие из заказа), {details} (1-2 детали из описания)
    FALLBACK_TEMPLATE: str = os.getenv(
        "FALLBACK_TEMPLATE",
        "Здравствуйте! Меня зовут Артём. Вижу, что вам нужен {action} — именно это и есть мой основной профиль. Уже решал похожие задачи: {details}. Готов взяться за работу, сделаю качественно и в срок. Напишите, пожалуйста, есть ли нюансы или пожелания по формату/срокам, и сразу назову стоимость. Жду ответа!"
    )

    # Ключевые слова для извлечения действия и деталей
    ACTION_KEYWORDS: list[dict] = [
        {"keywords": ["перевод", "перевести"], "action": "перевод текста", "details": "перевод с английского на русский, с сохранением смысла и стиля"},
        {"keywords": ["парсинг", "парсер", "сбор данных", "скрапинг"], "action": "парсинг и сбор данных", "details": "сбор цен, характеристик, фото, выгрузка в CSV/JSON/БД"},
        {"keywords": ["бот", "телеграм", "telegram", "tg"], "action": "разработка телеграм-бота", "details": "боты для записей, оплат, рассылок, интеграции с CRM"},
        {"keywords": ["лендинг", "landing"], "action": "создание лендинга", "details": "адаптивная вёрстка, структуры по AIDA, формы лидов, CRM"},
        {"keywords": ["сайт", "веб", "web", "интернет-магазин"], "action": "разработка сайта", "details": "WordPress, Tilda, чистый код, адаптив, SEO-база"},
        {"keywords": ["дизайн", "ui", "ux", "фигма", "figma", "креатив", "баннер"], "action": "дизайн", "details": "UI/UX интерфейсы, баннеры, креативы для рекламы, Figma исходники"},
        {"keywords": ["автоматизац", "скрипт", "скрипты", "синхронизац"], "action": "автоматизация", "details": "скрипты для сбора данных, синхронизация CRM/маркетплейсы/таблицы"},
        {"keywords": ["интеграц", "api", "amo", "bitrix", "wildberries", "ozon"], "action": "интеграция", "details": "подключение CRM, маркетплейсов, Telegram, почты через API"},
        {"keywords": ["видео", "монтаж", "reels", "shorts", "ютуб", "youtube"], "action": "видеомонтаж", "details": "Reels/Shorts/YouTube, Premiere/After Effects, субтитры, музыка"},
        {"keywords": ["текст", "статья", "пост", "контент", "копирайтинг", "сео", "seo"], "action": "написание текстов", "details": "статьи, посты для соцсетей, SEO-тексты, коммерческие предложения"},
        {"keywords": ["логтип", "лого", "брендбук", "брендинг", "айдентика"], "action": "дизайн логотипа и айдентики", "details": "логотип, гайдлайн, фирменный стиль, исходники"},
    ]

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