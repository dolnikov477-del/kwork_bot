import os
import re
import asyncio
import random
import logging
from typing import Tuple, Optional

from config import settings

logger = logging.getLogger(__name__)

USE_AI = os.getenv("USE_AI", "false").lower() == "true"

types = None
_client = None

# Semaphore для ограничения параллелизма запросов к Gemini
_gemini_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _gemini_semaphore
    if _gemini_semaphore is None:
        _gemini_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)
    return _gemini_semaphore


if USE_AI:
    try:
        from google import genai
        from google.genai import types

        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        GEMINI_PROXY_URL = os.getenv("GEMINI_PROXY_URL", "")

        if GEMINI_API_KEY:
            if GEMINI_PROXY_URL:
                _client = genai.Client(
                    api_key=GEMINI_API_KEY,
                    http_options=types.HttpOptions(base_url=GEMINI_PROXY_URL),
                )
                logger.info("Gemini API настроен через прокси: %s", GEMINI_PROXY_URL)
            else:
                _client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini API настроен (прямой доступ, нужен VPN)")
        else:
            logger.warning("USE_AI=true, но GEMINI_API_KEY не задан")
    except ImportError:
        logger.warning("google-genai не установлен, ИИ отключён")
else:
    logger.info("ИИ отключён (USE_AI=false).")


# ВАЖНО: впишите сюда только реальные кейсы. ИИ будет ссылаться на них в откликах.
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


SYSTEM_TEMPLATE = """Ты {name}, фрилансер на Кворке. Ты пишешь отклик на заказ, который тебя заинтересовал.
Заказчик получает десятки однотипных откликов и выбирает того, кто сразу показал, что вник в его задачу. Твоя цель, чтобы он открыл твой профиль и ответил.

ПРОФИЛЬ (единственный источник фактов о тебе)
Специализация: {specialization}
Кейсы:
{cases}
Типичные сроки: {terms}
Никаких других фактов о себе, клиентов, цифр, инструментов и опыта придумывать нельзя.

КАК ПОСТРОИТЬ ОТКЛИК
1. Начни с «Здравствуйте» или «Добрый день» и сразу «меня зовут {name}».
2. Своими словами назови, что именно заказчик хочет получить, и включи 1-2 конкретные детали из описания (платформа, объём, интеграция, формат). Это главное, ради чего читают отклик.
3. Покажи, что ты думаешь над задачей. Назови одно соображение по существу именно этого заказа: где обычно возникают проблемы, что важно учесть, с чего ты начнёшь работу.
4. Если в профиле есть кейс, который действительно близок к задаче, упомяни его одним предложением вместе с результатом. Если близкого кейса нет, не упоминай кейсы совсем. Без кейса лучше, чем с натяжкой.
5. Срок: назови, если его можно оценить по типичным срокам из профиля. Цену называй, только если заказчик указал бюджет, и не спорь о ней.
6. Задай один уточняющий вопрос, ответ на который реально меняет подход к работе. Не «какие у вас пожелания».
7. Закончи конкретным шагом с твоей стороны, который ты сделаешь сегодня или сразу после ответа.

ТОН
Пиши как живой человек в мессенджере: просто, спокойно, уверенно, на «вы». Без лести и канцелярита. Не хвали себя прилагательными, показывай делом: детали задачи, подход, цифры из кейсов.

ФОРМАТ
Один абзац без переносов строк, 4-6 предложений, 450-800 символов.
Только запятые и точки. Без тире между словами, восклицательных знаков, двоеточий, точек с запятой, кавычек, скобок, эмодзи, списков и markdown. Дефис допустим внутри слов и в диапазонах чисел, например 3-4 дня.
Иностранные слова пиши по-русски: телеграм, вордпресс, интерфейс, сайт, дедлайн, фидбэк, дизайн, фигма.
Ты обычный человек, поэтому не упоминай ИИ, нейросеть, модель и шаблон.

НЕ ПИШИ
Слова и обороты: качественно, оперативно, ответственно, профессионально, под ключ, гарантирую, любой сложности, большой опыт, в кратчайшие сроки, внимательно изучил, готов приступить, буду рад, конечно, я бы хотел.
Предложения, которые подошли бы к любому заказу. Каждое предложение привязано к этому заказу или к кейсу из профиля.
Повторы одной мысли разными словами.

ПРИМЕРЫ СТИЛЯ
Это примеры построения и тона. Не копируй формулировки. Факты о себе бери только из профиля выше.

Заказ: Нужен телеграм-бот для записи клиентов в барбершоп, три мастера, нужны напоминания.
Отклик: Здравствуйте, меня зовут Артём. Вижу, что клиенты должны сами выбирать мастера и время, а вы получать записи без звонков. Делал такого бота для барбершопа, записей стало на 30% больше, а пропусков меньше за счёт напоминаний. Для трёх мастеров главное правильно считать свободные окна с учётом длительности услуг, это заложу в расписание сразу, и по срокам выйдет 3-5 дней. Нужна ли выгрузка записей в гугл таблицу или вам хватит уведомлений в телеграм? Сегодня пришлю схему диалога бота, чтобы вы поправили её до начала работы.

Заказ: Спарсить карточки товаров с маркетплейса, около 100 тысяч позиций, выгрузка в таблицу раз в сутки.
Отклик: Добрый день, меня зовут Артём. Вам нужно собирать около 100 тысяч карточек раз в сутки и получать их в таблице. Похожий парсер для маркетплейса я делал, он обрабатывает 50 тысяч товаров в сутки с экспортом в CSV. На таком объёме обычно упираются в блокировки по частоте запросов, поэтому сразу заложу очередь и повтор при ошибках, первую версию сделаю за 1-2 дня. С какой площадки нужны данные и какие поля важны, только цена и наличие или ещё характеристики? Как узнаю площадку, сегодня же проверю, можно ли собирать её стабильно, и напишу вам результат.

Заказ: На сайте перестала работать форма заявки, письма не приходят на почту.
Отклик: Здравствуйте, меня зовут Артём. Если форма отправляется, а письма не доходят, причина обычно в настройках отправки почты на хостинге или в том, что письма уходят в спам. Сначала найду, где именно обрывается цепочка, на сайте, при отправке или у почтового сервиса, потом исправлю и проверю на нескольких адресах. Обычно такая поломка решается за день. На чём сделан сайт и когда форма работала в последний раз? Пришлите, пожалуйста, доступ к админке или хостингу, и сегодня я скажу, в чём причина."""


def build_system_prompt() -> str:
    cases = "\n".join(f"- {c}" for c in PROFILE["cases"])
    return SYSTEM_TEMPLATE.format(
        name=PROFILE["name"],
        specialization=PROFILE["specialization"],
        cases=cases,
        terms=PROFILE["typical_terms"],
    )


def build_user_prompt(title: str, description: str, price: str) -> str:
    return (
        "Заказ на Кворке\n"
        f"Название: {title.strip()}\n"
        f"Описание: {description.strip()[:3000]}\n"
        f"Бюджет: {price or 'не указан'}\n\n"
        "Напиши отклик. Выдай только текст отклика, без пояснений."
    )


def build_fallback_reply(title: str) -> str:
    """Строит системный отклик по шаблону из конфига."""
    return settings.FALLBACK_TEMPLATE.format(title=title)


# ---------- Постобработка и проверка ----------

EN_WORDS = {
    "telegram": "телеграм", "wordpress": "вордпресс", "api": "интерфейс",
    "bot": "бот", "web": "сайт", "deadline": "дедлайн", "feedback": "фидбэк",
    "design": "дизайн", "figma": "фигма", "amvera": "амвера",
}

BANNED = [
    "качественно", "оперативно", "ответственно", "профессионально", "под ключ",
    "гарантирую", "любой сложности", "большой опыт", "кратчайш", "внимательно изуч",
    "буду рад", "готов приступить", "опытная команда", "ориентируясь на результат",
    "не бросаю", "конечно", "я бы хотел", "нейросет", "искусственн",
]


def clean_reply(text: str) -> str:
    t = text.strip()
    t = re.sub(r"[*_`#>]+", "", t)                                   # markdown
    t = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf]", "", t)       # эмодзи
    t = re.sub(r"\s*[—–]\s*", ", ", t)                               # тире
    t = re.sub(r"\s+-\s+", ", ", t)
    t = t.replace("!", ".").replace(";", ",")
    t = re.sub(r"(?<!\d):|:(?!\d)", ",", t)                          # двоеточия (кроме 12:00)
    t = re.sub(r"[«»\"“”]", "", t)                                   # кавычки
    for en, ru in EN_WORDS.items():
        t = re.sub(rf"\b{en}\b", ru, t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\n\s*", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r",\s*([.,])", r"\1", t)
    t = re.sub(r"\.{2,}", ".", t)
    t = re.sub(r"\s+([,.?])", r"\1", t)
    return t.strip()


def find_problems(text: str) -> list[str]:
    problems = []
    low = text.lower()
    for w in BANNED:
        if w in low:
            problems.append(f"Убери выражение «{w}».")
    n = len(text)
    if n < 350:
        problems.append("Отклик слишком короткий, нужно 450-800 символов.")
    if n > 900:
        problems.append("Отклик слишком длинный, нужно 450-800 символов.")
    if not re.match(r"(Здравствуйте|Добрый день)", text):
        problems.append("Начни с «Здравствуйте» или «Добрый день».")
    if f"меня зовут {PROFILE['name']}".lower() not in low:
        problems.append(f"Представься: «меня зовут {PROFILE['name']}».")
    if "?" not in text:
        problems.append("Добавь один уточняющий вопрос по заказу.")
    return problems


# Коды ошибок, при которых делаем ретрай
RETRYABLE_STATUS_CODES = {429, 500, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}


def _is_retryable_error(e: Exception) -> bool:
    """Определяет, стоит ли ретраить при данной ошибке."""
    # Сетевые ошибки и таймауты
    if isinstance(e, (asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    # Ошибки Google GenAI SDK
    if hasattr(e, "status_code"):
        return e.status_code in RETRYABLE_STATUS_CODES
    # Проверяем по тексту ошибки (для обёрток)
    err_text = str(e).lower()
    if any(code in err_text for code in ("429", "500", "503", "504")):
        return True
    if any(code in err_text for code in ("400", "401", "403", "404")):
        return False
    # По умолчанию ретраим на неизвестные ошибки
    return True


async def _try_generate_with_model(
    model: str,
    system_prompt: str,
    user_prompt: str,
    attempt: int,
    max_attempts: int,
    order_title: str,
) -> Optional[str]:
    """Пытается сгенерировать отклик конкретной моделью с ретраями."""
    if _client is None or types is None:
        return None

    semaphore = _get_semaphore()

    for attempt_num in range(1, max_attempts + 1):
        async with semaphore:
            # Небольшая задержка перед стартом запроса для сглаживания всплесков
            if settings.REQUEST_START_DELAY > 0:
                await asyncio.sleep(random.uniform(0, settings.REQUEST_START_DELAY))

            try:
                logger.info(
                    "Вызываю Gemini (model=%s, attempt=%d/%d, order=%s)",
                    model, attempt_num, max_attempts, order_title
                )
                cfg = dict(
                    system_instruction=system_prompt,
                    temperature=0.8,
                    top_p=0.95,
                    max_output_tokens=3000,
                )
                if "2.5" in model:
                    cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=512)
                config = types.GenerateContentConfig(**cfg)

                response = await _client.aio.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config,
                )
            except Exception as e:
                # Проверяем, ретраить ли
                if _is_retryable_error(e):
                    status_code = getattr(e, "status_code", None)
                    logger.warning(
                        "Gemini ошибка (model=%s, attempt=%d/%d, order=%s): %s (ретраим)",
                        model, attempt_num, settings.MAX_ATTEMPTS_PER_MODEL, order_title, e
                    )
                    if attempt_num < settings.MAX_ATTEMPTS_PER_MODEL:
                        # Экспоненциальная задержка с джиттером: min(2**attempt, 30) + random(0, 1.5)
                        delay = min(2 ** attempt_num, 30) + random.uniform(0, 1.5)
                        logger.debug("Жду %.1f сек перед ретраем", delay)
                        await asyncio.sleep(delay)
                        continue
                else:
                    # Не ретраим - это ошибка модели/ключа/доступа
                    logger.error(
                        "Gemini неретраимовая ошибка (model=%s, order=%s): %s",
                        model, order_title, e
                    )
                    return None
                continue

            raw = (response.text or "").strip()
            logger.info("=== СЫРОЙ ОТВЕТ (model=%s) ===\n%s", model, raw)

            if not raw:
                logger.warning("Пустой ответ модели (model=%s, attempt=%d, order=%s)", model, attempt_num, order_title)
                if attempt_num < settings.MAX_ATTEMPTS_PER_MODEL:
                    delay = min(2 ** attempt_num, 30) + random.uniform(0, 1.5)
                    await asyncio.sleep(delay)
                continue

            text = clean_reply(raw)
            problems = find_problems(text)

            if not problems:
                logger.info(
                    "Отклик принят (model=%s, %d символов, order=%s): %s",
                    model, len(text), order_title, text
                )
                return text

            logger.warning("Проблемы в отклике (model=%s): %s", model, problems)
            if attempt_num < settings.MAX_ATTEMPTS_PER_MODEL:
                delay = min(2 ** attempt_num, 30) + random.uniform(0, 1.5)
                await asyncio.sleep(delay)

    return None


async def generate_reply(title: str, description: str, price: str = "") -> Tuple[str, str]:
    """
    Генерирует отклик через Gemini с fallback цепочкой моделей.
    Возвращает (text, source) где source = "ai" или "fallback_template".
    """
    if not title or not title.strip():
        logger.error("Пустой заголовок заказа")
        return "Ошибка: не указан заголовок заказа", "fallback_template"

    if not description or not description.strip():
        logger.error("Пустое описание заказа")
        return "Ошибка: не указано описание заказа", "fallback_template"

    if _client is None or types is None:
        logger.error("ИИ клиент не инициализирован (USE_AI=false или нет GEMINI_API_KEY)")
        fallback = build_fallback_reply(title)
        return fallback, "fallback_template"

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(title, description, price)
    logger.info("=== USER PROMPT ===\n%s", user_prompt)

    # Пробуем модели по порядку
    for model_idx, model in enumerate(settings.GEMINI_MODELS):
        logger.info("Пробую модель %d/%d: %s (order=%s)", model_idx + 1, len(settings.GEMINI_MODELS), model, title)

        result = await _try_generate_with_model(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            attempt=1,
            max_attempts=settings.MAX_ATTEMPTS_PER_MODEL,
            order_title=title,
        )

        if result:
            logger.info("Заказ %s: отклик сгенерирован моделью %s (source=ai)", title, model)
            return result, "ai"

        logger.warning("Модель %s не дала результата для заказа %s, переходим к следующей", model, title)

    # Все модели провалились - используем системный шаблон
    fallback = build_fallback_reply(title)
    logger.error("Заказ %s: ИИ не ответил, использован шаблон (source=fallback_template)", title)
    return fallback, "fallback_template"