import os
import logging
import httpx
import json

from config import settings

logger = logging.getLogger(__name__)

# YandexGPT configuration
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_MODEL = os.getenv("YANDEX_MODEL", "yandexgpt-lite")  # или yandexgpt

_yandex_client: httpx.AsyncClient | None = None


def _get_yandex_client() -> httpx.AsyncClient | None:
    global _yandex_client
    if _yandex_client is None and YANDEX_API_KEY and YANDEX_FOLDER_ID:
        _yandex_client = httpx.AsyncClient(
            base_url="https://llm.api.cloud.yandex.net/foundationModels/v1",
            headers={
                "Authorization": f"Api-Key {YANDEX_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        logger.info("YandexGPT настроен, модель: %s, folder_id: %s", YANDEX_MODEL, YANDEX_FOLDER_ID[:10] + "...")
    return _yandex_client


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


async def generate_reply(title: str, description: str, price: str = "") -> str:
    """Генерация отклика через YandexGPT."""
    client = _get_yandex_client()
    if client is None:
        logger.error("YANDEX_API_KEY или YANDEX_FOLDER_ID не настроены")
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

    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_MODEL}",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 1200,
        },
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": user_prompt},
        ],
    }

    max_retries = 3
    base_delay = 2.0

    for i in range(max_retries):
        try:
            logger.info("Вызываю YandexGPT (попытка %d/%d)...", i + 1, max_retries)
            response = await client.post("/completion", json=payload)

            if response.status_code != 200:
                logger.error("YandexGPT error %d: %s", response.status_code, response.text)
                if i < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(base_delay)
                continue

            data = response.json()
            reply_text = data.get("result", {}).get("alternatives", [{}])[0].get("message", {}).get("text", "").strip()

            logger.info("Получен ответ от YandexGPT для заказа '%s': %d символов", title, len(reply_text))

            if reply_text:
                return reply_text
            else:
                logger.warning("Получен пустой ответ от YandexGPT (попытка %d/%d)", i + 1, max_retries)

        except Exception as e:
            logger.error("YandexGPT error (попытка %d/%d): %s", i + 1, max_retries, e)
            if i < max_retries - 1:
                import asyncio
                await asyncio.sleep(base_delay)

    logger.error("Не удалось получить ответ от YandexGPT после %d попыток", max_retries)
    return ""