from openai import OpenAI
import httpx
import os

from config import settings
import logging
import time

logger = logging.getLogger(__name__)

_http_client = None
if settings.PROXY_URL:
    _http_client = httpx.Client(proxy=settings.PROXY_URL)
    logger.info("Используется прокси: %s", settings.PROXY_URL)

_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url=os.getenv("GROQ_BASE_URL", "https://openrouter.ai/api/v1"),
    http_client=_http_client,
)
default_model = os.getenv("GROQ_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
logger.info("AI client base_url: %s, model: %s", _client.base_url, default_model)


# Системный промт для естественных откликов фрилансера
SYSTEM_PROMPT = """Ты — Артём, фрилансер. Пишешь отклик на заказ на Kwork. Пиши просто, как человек в чате.

СТРОГО ЗАПРЕЩЕНО:
— НИКОГДА не используй знак ТИРЕ (—) ни в каком виде. ЭТОТ ЗНАК ЗАПРЕЩЁН ПОЛНОСТЬЮ. Используй только запятые, точки, вопросительные знаки.
— НИКОГДА не используй короткие тире (-) и длинные тире (–). Забудь про их существование.
— НИКОГДА не используй эмодзи, звёздочки, markdown.
— НИКОГДА не пиши "здравствуйте", "добрый день", "меня зовут артём из файнд/агентства".
— НИКОГДА не пиши клише: "качественно", "под ключ", "опытная команда", "гарантирую", "профессионально".
— НИКОГДА не используй английские слова: telegram → телеграм, wordpress → вордпресс, api → интерфейс, bot → бот, web → сайт.

СТИЛЬ:
— Пиши развёрнуто, по существу. 5-8 предложений.
— Представься просто: "Артём".
— Подробно опиши, что понял в задаче (2-3 предложения).
— Конкретно напиши, что сделаешь и как подойдёшь к решению.
— Объясни, почему справишься (опыт, навыки, похожие проекты).
— Если есть неясность — задай уточняющий вопрос.
— Без воды, но с понятным объёмом и конкретикой.
"""


def generate_reply(title: str, description: str, price: str = "") -> str:

    user_prompt = (
        f"Заголовок: {title}\n"
        f"Описание: {description}\n"
        f"Бюджет: {price or 'не указан'}\n\n"
        "Напиши отклик от Артёма. Структура: имя, подробно что понял в задаче, что конкретно сделаешь и как, почему справишься (опыт/навыки), вопрос если нужно. 5-8 предложений. Никаких тире вообще. Без приветствий."
    )

    models = [default_model, "meta-llama/llama-3.1-8b-instruct:free"]
    max_retries = 3
    base_delay = 2.0

    for model_name in models:
        for i in range(max_retries):
            try:
                logger.info("Вызываю OpenRouter с моделью '%s'... (попытка %d/%d)", model_name, i + 1, max_retries)
                completion = _client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1200,
                    timeout=30.0,
                )

                reply_text = completion.choices[0].message.content.strip()
                logger.info("Получен ответ от AI для заказа '%s': %d символов", title, len(reply_text))

                if reply_text:
                    return reply_text
                else:
                    logger.warning("Получен пустой ответ от AI (попытка %d/%d)", i + 1, max_retries)

            except Exception as e:
                logger.error("OpenRouter error с моделью '%s' (попытка %d/%d): %s", model_name, i + 1, max_retries, e)
                if i < max_retries - 1:
                    logger.info("Ожидание %.1f секунд перед повторной попыткой", base_delay)
                    time.sleep(base_delay)

    logger.error("Не удалось получить ответ от AI после %d попыток по всем моделям", max_retries)
    return ""