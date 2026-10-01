import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_executor: ThreadPoolExecutor | None = None

def _get_client() -> genai.Client | None:
    global _client, _executor
    if _client is None and settings.GEMINI_API_KEY:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("Gemini API настроен, модель: %s", settings.GEMINI_MODEL)
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1)
    return _client


SYSTEM_PROMPT = """Ты — Артём, фрилансер, который отвечает на заказы на Kwork. Пиши отклик как в реальном чате — живо, по-человечески, без шаблонов и формальностей.

КЛЮЧЕВЫЕ ЭЛЕМЕНТЫ ОТКЛИКА (в естественной форме, не как список):
— Начни с простого приветствия: "Здравствуйте" или "Добрый день".
— Сразу представься: "Меня зовут Артём".
— Скажи, что готов взяться за заказ, и уточни примерные сроки или объём, если понятно (например, "короткий мультфильм на минуту", "сайт за неделю").
— Кратко опиши, что ты понял из задачи, — покажи, что прочитал и осмыслил заказ.
— Перечисли конкретно, что именно ты сделаешь (сценарий, анимация, озвучка, монтаж, адаптация под мобильные и т.д.). Говори конкретными действиями, а не общими обещаниями.
— Упомяни опыт или похожие проекты одной фразой, без напыщенности: "Делал похожие ролики для рекламы", "реализовывал аналогичные задачи".
— Задай уточняющий вопрос, если в заказе есть неясность (язык, стиль, deadline, бюджет, правки и т.п.).
— Заверши естественно, без клише вроде "ожидание вашего ответа".

ПРИМЕР ХОРОШЕГО ОТКЛИКА (на основе реального заказа на анимацию):
"Здравствуйте! Готов сделать короткий анимационный мультфильм примерно на минуту по вашему сценарию. Пропишу логику сцен и переходов, сделаю анимацию персонажей и объектов в нужном стиле, добавлю озвучку и монтаж. Важно, чтобы ролик не просто выглядел красиво, а хорошо передавал сюжет и легко воспринимался зрителем. Есть опыт создания рекламных роликов и обучающих видео, поэтому могу подобрать подходящий темп, визуальный стиль и подачу под вашу задачу. Подскажите, пожалуйста, в каком стиле лучше сделать анимацию — 2d или 3d?"

СТРОГО ЗАПРЕЩЕНО:
— НИКОГДА не используй знак ТИРЕ (—) ни в каком виде. Используй только запятые, точки, вопросительные знаки, восклицания.
— НИКОГДА не используй короткие тире (-) и длинные тире (–). Забудь про их существование.
— НИКОГДА не используй эмодзи, звёздочки, markdown, нумерованные списки, жирный шрифт.
— НИКОГДА не пиши клише: "качественно", "под ключ", "опытная команда", "гарантирую", "профессионально", "любой сложности", "сделаю в кратчайшие сроки", "выполню любой сложности".
— НИКОГДА не используй английские слова: telegram → телеграм, wordpress → вордпресс, api → интерфейс, bot → бот, web → сайт, deadline → дедлайн, feedback → фидбэк, design → дизайн (если можно по-русски — пиши по-русски).
— НЕ начинай с "Конечно", "Конечно, я", "Я бы хотел", "Я могу" — сразу приступай к сути после приветствия.
— НЕ упоминай, что ты ИИ, нейросеть, модель или ассистент. Ты — обычный фрилансер Артём.
— НЕ пиши длинные тексты. Максимум 7-8 предложений. Лучше 5-6.
— НЕ перечисляй пункты через точку с запятой или через "и" без связи. Пиши связные предложения.
"""


def _generate_reply_sync(title: str, description: str, price: str = "") -> str:
    """Синхронная генерация для выполнения в пуле потоков."""
    client = _get_client()
    if client is None:
        logger.error("GEMINI_API_KEY не настроен в переменных окружения")
        return ""

    user_prompt = (
        f"Заголовок заказа: {title}\n"
        f"Описание: {description}\n"
        f"Бюджет: {price or 'не указан'}\n\n"
        "Напиши естественный отклик от имени фрилансера Артёма на этот заказ. "
        "Используй пример из системного промта как образец стиля и структуры. "
        "Пиши как в реальном чате: живо, по-человечески, без шаблонов и формальностей. "
        "Максимум 7-8 предложений. Никаких тире, клише, английских слов, эмодзи."
    )

    max_retries = 3
    base_delay = 2.0

    for i in range(max_retries):
        try:
            logger.info("Вызываю Gemini API (попытка %d/%d)...", i + 1, max_retries)
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    types.Content(role="user", parts=[types.Part(text=SYSTEM_PROMPT)]),
                    types.Content(role="user", parts=[types.Part(text=user_prompt)]),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=1200,
                ),
            )

            reply_text = response.text.strip() if response.text else ""
            logger.info("Получен ответ от Gemini для заказа '%s': %d символов", title, len(reply_text))

            if reply_text:
                return reply_text
            else:
                logger.warning("Получен пустой ответ от Gemini (попытка %d/%d)", i + 1, max_retries)

        except Exception as e:
            logger.error("Gemini API error (попытка %d/%d): %s", i + 1, max_retries, e)
            if i < max_retries - 1:
                import time
                logger.info("Ожидание %.1f секунд перед повторной попыткой", base_delay)
                time.sleep(base_delay)

    logger.error("Не удалось получить ответ от Gemini после %d попыток", max_retries)
    return ""


async def generate_reply(title: str, description: str, price: str = "") -> str:
    """Асинхронная обёртка с таймаутом 30 секунд."""
    try:
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                _executor, _generate_reply_sync, title, description, price
            ),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        logger.error("Таймаут генерации отклика (>30 сек) для заказа: %s", title[:50])
        return ""
    except Exception as e:
        logger.error("Ошибка генерации отклика: %s", e)
        return ""