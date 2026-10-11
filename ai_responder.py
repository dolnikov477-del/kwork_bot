import logging
from typing import Tuple

from config import settings
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError, PermissionDeniedError

logger = logging.getLogger(__name__)


def _extract_action_and_details(title: str, description: str) -> Tuple[str, str]:
    """Извлекает действие и детали из title + description по ключевым словам."""
    text = f"{title} {description}".lower()

    for entry in settings.ACTION_KEYWORDS:
        for kw in entry["keywords"]:
            if kw in text:
                return entry["action"], entry["details"]

    import re
    verbs = ["сделать", "создать", "разработать", "написать", "спарсить", "перевести",
             "нарисовать", "смонтировать", "настроить", "интегрировать",
             "автоматизировать", "подготовить", "подобрать", "найти", "собрать"]
    for v in verbs:
        if v in title.lower():
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


def _build_prompt(title: str, description: str, price: str = "") -> str:
    """Формирует промпт для генерации отклика через ИИ."""
    parts = [
        "Ты — опытный фрилансер на Kwork. Напиши отклик на заказ клиента.",
        "",
        f"Название заказа: {title}",
    ]
    if description:
        parts.append(f"Описание: {description}")
    if price:
        parts.append(f"Бюджет: {price}")
    parts.extend([
        "",
        "Требования к отклику:",
        "- Пиши на русском языке, естественно и по делу.",
        "- Покажи понимание задачи и предложи конкретный подход.",
        "- Будь кратким, без воды и шаблонных фраз.",
        "- Не выдумывай опыт, портфолио, гарантии, которых нет в данных.",
        "- Не пиши, что задача уже выполнена.",
        "- Не добавляй пояснения от себя, заголовки, Markdown.",
        "- Верни только текст готового отклика для клиента.",
    ])
    return "\n".join(parts)


async def generate_reply(title: str, description: str, price: str = "") -> Tuple[str, str]:
    """Генерирует отклик через Groq API или возвращает шаблон как фоллбэк."""
    if not title or not title.strip():
        logger.error("Пустой заголовок заказа")
        return "Ошибка: не указан заголовок заказа", "fallback_template"

    if not settings.USE_AI:
        logger.info("USE_AI=false, использую шаблонный отклик")
        return build_fallback_reply(title, description), "fallback_template"

    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY не задан, использую шаблонный отклик")
        return build_fallback_reply(title, description), "fallback_template"

    client = AsyncOpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    prompt = _build_prompt(title, description, price)

    try:
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Ты пишешь отклики на заказы фрилансера. Только текст отклика, без лишних слов."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
            timeout=30.0,
        )

        reply_text = response.choices[0].message.content
        if not reply_text or not reply_text.strip():
            logger.warning("Пустой ответ от Groq API, использую шаблон")
            return build_fallback_reply(title, description), "fallback_template"

        reply_text = reply_text.strip()
        logger.info("Groq отклик для заказа %s (%d символов, модель=%s)", title[:50], len(reply_text), settings.GROQ_MODEL)
        return reply_text, "ai"

    except AuthenticationError:
        logger.error("Groq API: ошибка аутентификации (неверный API ключ). Использую шаблон.")
        return build_fallback_reply(title, description), "fallback_template"
    except PermissionDeniedError:
        logger.error("Groq API: доступ запрещён (403 Forbidden). Проверьте настройки сети/VPN/региона. Использую шаблон.")
        return build_fallback_reply(title, description), "fallback_template"
    except RateLimitError as e:
        logger.warning("Groq API: превышен лимит запросов (%s). Использую шаблон.", e)
        return build_fallback_reply(title, description), "fallback_template"
    except APIConnectionError as e:
        logger.warning("Groq API: ошибка соединения (%s). Использую шаблон.", e)
        return build_fallback_reply(title, description), "fallback_template"
    except APIError as e:
        logger.error("Groq API: ошибка API (%s). Использую шаблон.", e)
        return build_fallback_reply(title, description), "fallback_template"
    except Exception as e:
        logger.error("Groq API: неожиданная ошибка (%s). Использую шаблон.", e)
        return build_fallback_reply(title, description), "fallback_template"