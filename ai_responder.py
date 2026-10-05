import logging
from typing import Tuple

from config import settings

logger = logging.getLogger(__name__)


def _extract_action_and_details(title: str, description: str) -> Tuple[str, str]:
    """Извлекает действие и детали из title + description по ключевым словам."""
    text = f"{title} {description}".lower()

    for entry in settings.ACTION_KEYWORDS:
        for kw in entry["keywords"]:
            if kw in text:
                return entry["action"], entry["details"]

    # Фоллбэк — пробуем выхватить глагол из начала title
    import re
    verbs = ["сделать", "создать", "разработать", "написать", "спарсить", "спарсить", "перевести",
             "нарисовать", "нарисовать", "смонтировать", "смонтировать", "настроить", "интегрировать",
             "автоматизировать", "разработать", "подготовить", "подобрать", "найти", "собрать"]
    for v in verbs:
        if v in title.lower():
            # Выхватываем пару слов после глагола
            match = re.search(rf"{v}\s+(.+?)(?:\.|,|$)", title.lower())
            detail = match.group(1)[:60] if match else "данную задачу"
            return v, detail

    return "решение вашей задачи", "подготовку качественного результата в срок"


def build_fallback_reply(title: str, description: str = "") -> str:
    """Строит отклик, подставляя action и details."""
    action, details = _extract_action_and_details(title, description)
    return settings.FALLBACK_TEMPLATE.format(
        title=title,
        action=action,
        details=details
    )


async def generate_reply(title: str, description: str, price: str = "") -> Tuple[str, str]:
    """Возвращает отклик с подставленными action/details."""
    if not title or not title.strip():
        logger.error("Пустой заголовок заказа")
        return "Ошибка: не указан заголовок заказа", "fallback_template"

    action, details = _extract_action_and_details(title, description)
    reply = settings.FALLBACK_TEMPLATE.format(
        title=title,
        action=action,
        details=details
    )
    logger.info("Шаблонный отклик для заказа %s (action=%s, %d символов)", title, action, len(reply))
    return reply, "fallback_template"