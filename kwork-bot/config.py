import os

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-120b"
    )

    # Категории Kwork
    KWORK_CATEGORY_IDS: list[str] = _split_csv(
        os.getenv(
            "KWORK_CATEGORY_IDS",
            "38,39,41,79,113"
        )
    )

    # Ключевые слова для фильтрации заказов.
    # Заказ должен содержать хотя бы одно из этих слов
    # в title и/или description (без учёта регистра).
    KEYWORDS: list[str] = _split_csv(
        os.getenv("KEYWORDS", "")
    )

    # Интервал проверки новых заказов
    POLL_INTERVAL: int = int(
        os.getenv("POLL_INTERVAL", "90")
    )

    # База просмотренных заказов
    DB_PATH: str = os.getenv(
        "DB_PATH",
        "seen_orders.db"
    )


settings = Settings()
