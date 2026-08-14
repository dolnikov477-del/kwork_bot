import os

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    # Токен Telegram-бота (получить у @BotFather)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Твой chat_id (или ID канала/группы), куда бот шлёт уведомления.
    # Узнать свой ID можно у бота @userinfobot
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Ключ Groq (бесплатно на console.groq.com)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ID категорий Kwork через запятую. Смотри как узнать в README.
    # Пример: "39,41" (Разработка сайтов, Скрипты и боты)
    KWORK_CATEGORY_IDS: list[str] = _split_csv(os.getenv("KWORK_CATEGORY_IDS", "39"))

    # Ключевые слова для фильтра (через запятую, без учёта регистра)
    KEYWORDS: list[str] = _split_csv(
        os.getenv(
            "KEYWORDS",
            "сайт,лендинг,бот,телеграм бот,парсинг,парсер,автоматизация,интернет-магазин",
        )
    )

    # Как часто проверять новые заказы, в секундах
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "90"))

    # Путь к файлу базы (список уже виденных заказов)
    DB_PATH: str = os.getenv("DB_PATH", "seen_orders.db")


settings = Settings()
