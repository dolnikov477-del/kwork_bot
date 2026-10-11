import logging
from typing import Optional

from config import settings
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError, PermissionDeniedError

logger = logging.getLogger(__name__)


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


async def generate_reply(title: str, description: str, price: str = "") -> Optional[str]:
    """Генерирует отклик через Groq API. Возвращает None при ошибке."""
    if not title or not title.strip():
        logger.error("Пустой заголовок заказа")
        return None

    if not settings.USE_AI:
        logger.warning("USE_AI=false, генерация откликов отключена")
        return None

    if not settings.GROQ_API_KEY:
        logger.error("GROQ_API_KEY не задан")
        return None

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
            logger.warning("Пустой ответ от Groq API")
            return None

        reply_text = reply_text.strip()
        logger.info("Groq отклик для заказа %s (%d символов, модель=%s)", title[:50], len(reply_text), settings.GROQ_MODEL)
        return reply_text

    except AuthenticationError:
        logger.error("Groq API: ошибка аутентификации (неверный API ключ)")
        return None
    except PermissionDeniedError:
        logger.error("Groq API: доступ запрещён (403 Forbidden). Проверьте настройки сети/VPN/региона")
        return None
    except RateLimitError as e:
        logger.warning("Groq API: превышен лимит запросов (%s)", e)
        return None
    except APIConnectionError as e:
        logger.warning("Groq API: ошибка соединения (%s)", e)
        return None
    except APIError as e:
        logger.error("Groq API: ошибка API (%s)", e)
        return None
    except Exception as e:
        logger.error("Groq API: неожиданная ошибка (%s)", e)
        return None