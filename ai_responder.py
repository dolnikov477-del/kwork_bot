import logging
from typing import Tuple

from config import settings

logger = logging.getLogger(__name__)


# Профиль для информации (не используется в шаблонах, но может пригодиться)
PROFILE = {
    "name": "Артём",
    "specialization": "веб-разработка, боты, парсинг, автоматизация",
    "cases": [
        "бот для барбершопа: записи выросли на 30%, пропуски снизились за счёт напоминаний",
        "парсер товаров для маркетплейса: 50 тысяч товаров в сутки, экспорт в CSV и API",
        "лендинг для стартапа: конверсия выросла в 2 раза, адаптивная вёрстка за 3 дня",
        "автоматизация CRM: интеграция амоСРМ с телеграм-ботом, заявки попадают в CRM сразу",
    ],
    "typical_terms": "бот за 3-5 дней, парсер за 1-2 дня, лендинг за 2-4 дня, интеграция за 2-3 дня",
}


def build_fallback_reply(title: str, description: str = "") -> str:
    """Выбирает шаблон по ключевым словам в title/description."""
    text = f"{title} {description}".lower()

    keyword_map = [
        ("бот", "бот"),
        ("парс", "парс"),
        ("лендинг", "лендинг"),
        ("сайт", "сайт"),
        ("дизайн", "дизайн"),
        ("автоматиз", "автоматиз"),
        ("интеграц", "интеграц"),
        ("видео", "видео"),
        ("сео", "seo"),
        ("текст", "текст"),
    ]

    for keyword, template_key in keyword_map:
        if keyword in text:
            template = settings.TEMPLATES_BY_KEYWORDS.get(template_key)
            if template:
                return template.format(title=title)

    return settings.FALLBACK_TEMPLATE.format(title=title)


async def generate_reply(title: str, description: str, price: str = "") -> Tuple[str, str]:
    """Возвращает релевантный шаблонный отклик."""
    if not title or not title.strip():
        logger.error("Пустой заголовок заказа")
        return "Ошибка: не указан заголовок заказа", "fallback_template"

    reply = build_fallback_reply(title, description)
    logger.info("Шаблонный отклик для заказа %s (%d символов)", title, len(reply))
    return reply, "fallback_template"