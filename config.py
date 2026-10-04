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

    # Системный шаблон отклика (fallback) — минимум 400 символов, без кавычек, как живое сообщение
    FALLBACK_TEMPLATE: str = os.getenv(
        "FALLBACK_TEMPLATE",
        "Здравствуйте! Меня зовут Артём. Имею релевантный опыт: разрабатывал телеграм-ботов, парсеров, автоматизировал бизнес-процессы, делал интеграции с CRM и маркетплейсами. Знаю типичные подводные камни и как их обойти, чтобы результат получился стабильным и в срок. Готов взяться за работу — напишите, что именно важно в вашем случае, и я назову точные сроки и стоимость. Жду ответа!"
    )

    # Специализированные шаблоны по ключевым словам (подстановка {title})
    TEMPLATES_BY_KEYWORDS: dict[str, str] = {
        "бот": (
            "Здравствуйте! Меня зовут Артём. Разрабатывал телеграм-боты под ключ: запись клиентов, оплата, интеграция с CRM, рассылки. "
            "Знаю, как сделать удобный интерфейс и стабильную архитектуру, чтобы бот не падал под нагрузкой. "
            "По вашему заказу «{title}» — напишите, какие функции критичны, и я назову сроки и стоимость. Жду ответа!"
        ),
        "парс": (
            "Здравствуйте! Меня зовут Артём. Писал парсеры для маркетплейсов, каталогов, каталогов товаров — сбор цены, остатков, характеристик, фото. "
            "Решаю блокировки, капчи, динамический контент, выгружаю в CSV, JSON, БД или API. "
            "По «{title}» — уточните источник и объём, назову сроки. Жду!"
        ),
        "сайт": (
            "Здравствуйте! Меня зовут Артём. Делаю сайты: лендинги, корпоративные, интернет-магазины на WordPress, Tilda, чистом HTML/CSS/JS. "
            "Адаптивная вёрстка, скорость загрузки, SEO-база, интеграция форм с CRM/Telegram. "
            "По «{title}» — напишите, на какой платформе и какие функции нужны, назову сроки и стоимость."
        ),
        "лендинг": (
            "Здравствуйте! Меня зовут Артём. Делаю лендинги под ключ: структура по AIDA, адаптив, быстрые формы, подключение аналитики и CRM. "
            "Сделаю за 2-4 дня. По «{title}» — пришлите ТЗ или референсы, обсудим детали и стоимость."
        ),
        "дизайн": (
            "Здравствуйте! Меня зовут Артём. Делаю UI/UX дизайн: интерфейсы приложений, дашборды, лендинги, баннеры, креативы для рекламы. "
            "Работаю в Figma, отдаю исходники и UI-кит. По «{title}» — уточните объём и референсы, назову сроки."
        ),
        "автоматиз": (
            "Здравствуйте! Меня зовут Артём. Автоматизирую рутину: сбор данных, синхронизация CRM/маркетплейсы/таблицы, скрипты, вебхуки, интеграции API. "
            "Экономию времени — от часов до дней в неделю. По «{title}» — опишите процесс, который хотите автоматизировать."
        ),
        "интеграц": (
            "Здравствуйте! Меня зовут Артём. Настраиваю интеграции: amoCRM, Bitrix24, Wildberries, Ozon, Яндекс.Маркет, Telegram, почта, SMS-шлюзы. "
            "Работаю через API, вебхуки, делаю надёжную обработку ошибок. По «{title}» — какие системы соединяем?"
        ),
        "видео": (
            "Здравствуйте! Меня зовут Артём. Монтирую видео: рекламные ролики, Reels/Shorts, обучающие, для YouTube и соцсетей. "
            "Работаю в Premiere/After Effects, есть стоковые библиотеки. По «{title}» — пришлите примеры стиля и ТЗ."
        ),
        "текст": (
            "Здравствуйте! Меня зовут Артём. Пишу тексты: статьи, посты для соцсетей, SEO-статьи, коммерческие предложения, email-рассылки. "
            "Работаю с разными нишами, соблюдаю ТЗ и тонкости площадки. По «{title}» — тема, объём и дедлайн?"
        ),
        "seo": (
            "Здравствуйте! Меня зовут Артём. Занимаюсь SEO: технический аудит, семантическое ядро, кластеризация, контент-план, мета-теги, внутренняя перелинковка. "
            "Работаю с Яндекс и Google. По «{title}» — пришлите сайт или нишу, сделаю быстрый аудит и назову план."
        ),
    }

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