import os
import logging

from config import settings

logger = logging.getLogger(__name__)

# Проверяем, включён ли ИИ
USE_AI = os.getenv("USE_AI", "false").lower() == "true"

# Если ИИ включён — пробуем подключить Gemini
if USE_AI:
    try:
        from google import genai
        from google.genai import types
        
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        GEMINI_PROXY_URL = os.getenv("GEMINI_PROXY_URL", "")  # Cloudflare Worker URL
        
        if GEMINI_API_KEY:
            if GEMINI_PROXY_URL:
                _client = genai.Client(
                    api_key=GEMINI_API_KEY,
                    http_options=types.HttpOptions(base_url=GEMINI_PROXY_URL)
                )
                logger.info("Gemini API настроен через прокси: %s", GEMINI_PROXY_URL)
            else:
                _client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini API настроен (прямой доступ, нужен VPN)")
        else:
            _client = None
            logger.warning("USE_AI=true, но GEMINI_API_KEY не задан")
    except ImportError:
        _client = None
        logger.warning("google-genai не установлен, ИИ отключён")
else:
    _client = None
    logger.info("ИИ отключён (USE_AI=false). Используются шаблоны.")


SYSTEM_PROMPT = """Ты — Артём, фрилансер, который отвечает на заказы на Kwork. Пиши отклик как в реальном чате — живо, по-человечески, без шаблонов и формальностей.

ПРИМЕР ХОРОШЕГО ОТКЛИКА (ориентируйся по стилю, длине и структуре):
"Здравствуйте! Готов помочь с продвижением объявления о сдаче жилья. Могу отредактировать текст, сделать его более привлекательным и понятным для потенциальных арендаторов, а также помочь со сбором и анализом обратной связи. Работаю внимательно, ответственно и ориентируюсь на результат. Готов обсудить детали и приступить к выполнению в ближайшее время."

СТРОГО ЗАПРЕЩЕНО:
— НИКОГДА не используй тире (—) и короткие тире (-). Используй только запятые и точки.
— НИКОГДА не используй восклицательные знаки (!). Только запятые и точки.
— НИКОГДА не используй эмодзи, звёздочки, markdown, нумерованные списки, жирный шрифт.
— НИКОГДА не пиши клише: "качественно", "под ключ", "опытная команда", "гарантирую", "профессионально", "любой сложности", "сделаю в кратчайшие сроки", "выполню любой сложности".
— НИКОГДА не используй английские слова: telegram → телеграм, wordpress → вордпресс, api → интерфейс, bot → бот, web → сайт, deadline → дедлайн, feedback → фидбэк, design → дизайн, amvera → амвера (если можно по-русски — пиши по-русски).
— НЕ начинай с "Конечно", "Конечно, я", "Я бы хотел", "Я могу" — сразу приступай к сути после приветствия.
— НЕ упоминай, что ты ИИ, нейросеть, модель или ассистент. Ты — обычный фрилансер Артём.
— НЕ пиши короткие тексты. Пиши 6-9 предложений. Подробно, по сути.
— НЕ перечисляй пункты через точку с запятой или через "и" без связи. Пиши связные предложения.
— ОБЯЗАТЕЛЬНО начни с "Здравствуйте" или "Добрый день".
— ОБЯЗАТЕЛЬНО представься: "Меня зовут Артём".
— ОБЯЗАТЕЛЬНО скажи, чем конкретно можешь помочь по заказу.
— ОБЯЗАТЕЛЬНО задай уточняющий вопрос в конце (срок, бюджет, ТЗ, детали).
— Пиши только запятые и точки. Никаких тире, двоеточий, точек с запятой, восклицаний.
"""


# Умные шаблоны (работают без ИИ)
TEMPLATES = {
    "default": (
        "Здравствуйте, меня зовут Артём. Готов взяться за ваш заказ \"{title}\". "
        "Изучил описание, понимаю задачу. Могу помочь: разберу требования, предложу решение, "
        "реализую внимательно и ответственно, ориентируюсь на результат. "
        "Есть опыт похожих задач. Подскажите, есть ли ТЗ или макеты? Какой срок и бюджет планируете?"
    ),
    "web": (
        "Здравствуйте, меня зовут Артём, веб-разработчик. Вижу заказ \"{title}\" — готов сделать. "
        "Могу: верстка, бэкенд, API, админка, интеграции, деплой. Стек: Python, FastAPI, Django, JS, React, Vue, БД PostgreSQL, MySQL. "
        "Есть опыт подобных проектов, работаю внимательно и ответственно. "
        "Пришлите ТЗ или опишите задачу подробнее — обсудим сроки и бюджет."
    ),
    "bot": (
        "Здравствуйте, меня зовут Артём, делаю ботов и автоматизацию. Заказ \"{title}\" — в теме. "
        "Могу: телеграм-боты, вебхуки, FSM, платежи, парсинг, интеграции с CRM/API. "
        "Пишу на Python (aiogram). Есть готовые решения, работаю внимательно и ориентируюсь на результат. "
        "Напишите детали — обсудим срок и стоимость."
    ),
    "design": (
        "Здравствуйте, меня зовут Артём, дизайнер. Заказ \"{title}\" заинтересовал. "
        "Могу: UI/UX, макеты, прототипы, баннеры, презентации, айдентика. Инструменты: Figma. "
        "Есть портфолио, работаю внимательно и в срок. "
        "Пришлите референсы или опишите видение — обсудим."
    ),
    "text": (
        "Здравствуйте, меня зовут Артём, пишу тексты. Заказ \"{title}\" — могу выполнить. "
        "Пишу: статьи, SEO, карточки товаров, письма, посты. Без воды, по делу, в срок. "
        "Пришлите тему и требования — сделаю образец."
    ),
    "parsing": (
        "Здравствуйте, меня зовут Артём, парсинг и сбор данных. Заказ \"{title}\" — в работе. "
        "Могу: парсинг сайтов, API, структурирование данных, экспорт в CSV, Excel, JSON, БД. "
        "Обхожу защиту, работаю быстро. Пришлите источник и формат результата — оценю срок."
    ),
}


def _pick_template(title: str, description: str) -> str:
    """Выбирает шаблон по ключевым словам в заголовке/описании."""
    text = f"{title} {description}".lower()
    
    if any(w in text for w in ["бот", "bot", "телеграм", "telegram", "автоматизац", "парсинг", "parser", "скрипт", "script"]):
        return TEMPLATES["bot"]
    if any(w in text for w in ["сайт", "веб", "web", "верстка", "frontend", "backend", "бэкенд", "django", "fastapi", "react", "vue", "landing", "лендинг", "интернет-магазин"]):
        return TEMPLATES["web"]
    if any(w in text for w in ["дизайн", "design", "ui", "ux", "фигма", "figma", "макет", "баннер", "логотип", "бренд", "презентац"]):
        return TEMPLATES["design"]
    if any(w in text for w in ["текст", "статья", "seo", "контент", "копирайт", "описа", "пост", "карточк"]):
        return TEMPLATES["text"]
    if any(w in text for w in ["парсинг", "parser", "сбор данных", "скрапинг", "scraping", "выгрузк"]):
        return TEMPLATES["parsing"]
    
    return TEMPLATES["default"]


def _format_reply(template: str, title: str, price: str = "") -> str:
    """Подставляет переменные в шаблон."""
    reply = template.format(title=title)
    if price:
        reply += f" Бюджет: {price}."
    return reply


async def generate_reply(title: str, description: str, price: str = "") -> str:
    """Главная функция: пробует ИИ, если не вышло — шаблон."""
    
    # 1. Пробуем ИИ (если включено)
    if _client is not None:
        user_prompt = (
            f"Заголовок заказа: {title}\n"
            f"Описание: {description}\n"
            f"Бюджет: {price or 'не указан'}\n\n"
            "Напиши естественный отклик от имени фрилансера Артёма на этот заказ. "
            "Используй пример из системного промта как образец стиля, длины и структуры. "
            "Пиши как в реальном чате: живо, по-человечески, без шаблонов и формальностей. "
            "6-9 предложений. Никаких тире, восклицаний, английских слов, эмодзи. Только запятые и точки."
        )

        for attempt in range(3):
            try:
                logger.info("Вызываю Gemini API (попытка %d/3)...", attempt + 1)
                response = _client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=[
                        types.Content(role="user", parts=[types.Part(text=SYSTEM_PROMPT)]),
                        types.Content(role="user", parts=[types.Part(text=user_prompt)]),
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=1500,
                    ),
                )

                reply_text = response.text.strip() if response.text else ""
                
                if reply_text:
                    logger.info("Gemini ответил: %d символов", len(reply_text))
                    return reply_text
                    
            except Exception as e:
                logger.warning("Gemini ошибка (попытка %d/3): %s", attempt + 1, e)
                import asyncio
                await asyncio.sleep(2)
        
        logger.warning("Gemini не ответил, переключаюсь на шаблоны")

    # 2. Фоллбэк — умные шаблоны (всегда работают мгновенно)
    template = _pick_template(title, description)
    reply = _format_reply(template, title, price)
    logger.info("Использован шаблон: %s символов", len(reply))
    return reply