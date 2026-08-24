from groq import Groq
from groq import APIError, APIConnectionError, RateLimitError, InternalServerError

from config import settings
import logging
import random
import time

logger = logging.getLogger(__name__)

_client = Groq(api_key=settings.GROQ_API_KEY)

# Черновой системный промт. Дальше его будем дорабатывать под твой стиль/нишу.
SYSTEM_PROMPT = """\
Ты — Артём из агентства Файнд. Твоя задача — написать продающий отклик на заказ на бирже Kwork.

Структура отклика:
1. Приветствие: «Добрый день!» или «Здравствуйте!» (чередовать).
2. Представление: «Меня зовёт Артём, представляю агентство Файнд».
3. Зацепка: «Мы заинтересовались вашим заказом и уверены, что сможем качественно его реализовать».
4. Крючок (скидка): Обязательно добавь фразу: «Как уважаемым клиентам, мы готовы предложить вам скидку 10% на этот заказ».
5. Опыт: «У нас есть опыт в [тематика заказа], и мы знаем, как сделать это быстро и без лишних проблем».
6. Что сделаем: «Мы готовы оперативно выполнить [что именно нужно сделать] и сдать результат в срок».
7. Заключение: «Всегда на связи, готовы обсудить детали в любое время. Будем рады выполнить ваш заказ!».

Важно:
- Пункт 4 (скидка) — обязателен, но формулируй его естественно.
- Пиши живым языком, как в переписке с человеком.
- Не используй шаблонные фразы, будь конкретным.
- Не выдумывай портфолио, ссылки, цены или сроки — их допишет сам исполнитель.
"""


def generate_reply(title: str, description: str, price: str = "") -> str:
    user_prompt = (
        f"Заголовок заказа: {title}\n"
        f"Описание: {description}\n"
        f"Бюджет клиента: {price or 'не указан'}\n\n"
        "Напиши отклик на этот заказ."
    )

    max_retries = 3
    base_delay = 1.0
    
    for i in range(max_retries):
        try:
            completion = _client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=1200,
                timeout=30.0,  # 30 second timeout
            )

            reply_text = completion.choices[0].message.content.strip()
            logger.debug("Получен ответ от AI для заказа '%s': %d символов", title, len(reply_text))
            
            if reply_text:
                return reply_text
            else:
                logger.warning("Получен пустой ответ от AI (попытка %d/%d)", i + 1, max_retries)
                
        except RateLimitError as e:
            logger.warning("Превышен лимит запросов к Groq API (попытка %d/%d): %s", i + 1, max_retries, e)
            if i < max_retries - 1:
                delay = base_delay * (2 ** i) + random.uniform(0, 1)
                logger.info("Ожидание %.1f секунд перед повторной попыткой", delay)
                time.sleep(delay)
        except (APIConnectionError, InternalServerError) as e:
            logger.error("Ошибка соединения с Groq API (попытка %d/%d): %s", i + 1, max_retries, e)
            if i < max_retries - 1:
                delay = base_delay * (2 ** i) + random.uniform(0, 1)
                logger.info("Ожидание %.1f секунд перед повторной попыткой", delay)
                time.sleep(delay)
        except APIError as e:
            logger.error("Ошибка Groq API (попытка %d/%d): %s", i + 1, max_retries, e)
            # Don't retry on client errors (4xx)
            if i < max_retries - 1 and e.status_code >= 500:
                delay = base_delay * (2 ** i) + random.uniform(0, 1)
                logger.info("Ожидание %.1f секунд перед повторной попыткой", delay)
                time.sleep(delay)
            else:
                break
        except Exception as e:
            logger.exception("Неожиданная ошибка при вызове Groq API (попытка %d/%d): %s", i + 1, max_retries, e)
            if i < max_retries - 1:
                delay = base_delay * (2 ** i) + random.uniform(0, 1)
                logger.info("Ожидание %.1f секунд перед повторной попыткой", delay)
                time.sleep(delay)

    logger.error("Не удалось получить ответ от AI после %d попыток", max_retries)
    return ""