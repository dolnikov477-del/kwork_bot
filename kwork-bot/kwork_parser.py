"""
Парсер заказов Kwork через простой HTTP-запрос + BeautifulSoup.

Логика:
- при первом запуске запоминает все уже существующие заказы;
- старые заказы НЕ отправляет;
- после этого отправляет только заказы, которых раньше не видел.
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from config import settings
from storage import is_seen, save_order

logger = logging.getLogger(__name__)

KWORK_BASE_URL = "https://kwork.ru/projects"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

_ID_RE = re.compile(r"/projects/(\d+)")


def _parse_orders_from_html(html: str) -> list[dict]:
    """
    Разбирает HTML страницы категории и возвращает список заказов.
    """

    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select(".wants-card")

    orders: list[dict] = []

    for card in cards:
        link = card.select_one(
            ".wants-card__header-title a[href*='/projects/']"
        )

        if link is None:
            link = card.select_one("a[href*='/projects/']")

        href = link.get("href") if link else None

        id_match = _ID_RE.search(href) if href else None

        order_id = id_match.group(1) if id_match else None

        title_el = card.select_one(".wants-card__header-title")
        title = title_el.get_text(strip=True) if title_el else (
            link.get_text(strip=True) if link else ""
        )

        description_el = card.select_one(".wants-card__description-text")
        description = (
            description_el.get_text(strip=True) if description_el else ""
        )

        price_el = card.select_one(".wants-card__right")
        price = price_el.get_text(strip=True) if price_el else ""

        if not title or not order_id:
            continue

        url = (
            href
            if href.startswith("http")
            else f"https://kwork.ru{href}"
        ) if href else None

        orders.append(
            {
                "id": order_id,
                "title": title,
                "description": description,
                "price": price,
                "url": url,
            }
        )

    return orders


async def fetch_orders_for_category(category_id: str) -> list[dict]:
    """
    Получает заказы одной категории простым HTTP-запросом.
    """

    url = f"{KWORK_BASE_URL}?fc={category_id}"

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

    except Exception as e:
        logger.error(
            "Категория %s: ошибка HTTP-запроса: %s",
            category_id,
            e,
        )
        return []

    orders = _parse_orders_from_html(html)

    logger.info(
        "Категория %s: найдено карточек: %d",
        category_id,
        len(orders),
    )

    return orders


async def fetch_all_orders() -> list[dict]:
    """
    Получает все заказы из всех настроенных категорий
    через обычные HTTP-запросы (без браузера).
    """

    all_orders: list[dict] = []

    for category_id in settings.KWORK_CATEGORY_IDS:
        try:
            orders = await fetch_orders_for_category(category_id)

            all_orders.extend(orders)

        except Exception as e:
            logger.error(
                "Ошибка при обходе категории %s: %s",
                category_id,
                e,
            )

    # Убираем дубликаты, если один заказ попался
    # в нескольких категориях.
    unique_orders = {}

    for order in all_orders:
        order_id = order.get("id")

        if order_id:
            unique_orders[order_id] = order

    return list(unique_orders.values())


async def initialize_seen_orders() -> int:
    """
    Первый запуск.

    Все заказы, которые существуют прямо сейчас,
    считаются уже существующими.

    Они НЕ отправляются в Telegram.
    """

    logger.info(
        "Первичная инициализация базы: "
        "получаем текущие заказы..."
    )

    orders = await fetch_all_orders()

    added = 0

    for order in orders:
        order_id = order.get("id")

        if not order_id:
            continue

        if not is_seen(order_id):
            save_order(order)
            added += 1

    logger.info(
        "Первичная инициализация завершена. "
        "Добавлено старых заказов в базу: %d",
        added,
    )

    return added


def _matches_keywords(order: dict) -> bool:
    """
    Проверяет, содержит ли заказ хотя бы одно ключевое слово
    из settings.KEYWORDS в title и/или description
    (без учёта регистра).

    Если KEYWORDS пуст - фильтрация не применяется,
    и заказ считается подходящим.
    """

    keywords = settings.KEYWORDS

    if not keywords:
        return True

    title = (order.get("title") or "").lower()
    description = (order.get("description") or "").lower()

    text = f"{title} {description}"

    for keyword in keywords:
        if keyword.lower() in text:
            return True

    return False


async def fetch_new_orders() -> list[dict]:
    """
    Получает только новые заказы, подходящие по ключевым словам.

    Заказ считается новым, если его ID ещё нет
    в базе просмотренных заказов.

    Заказ добавляется в результат только если он
    содержит минимум одно ключевое слово из
    settings.KEYWORDS (в title и/или description).
    """

    logger.info("Парсинг заказов начат")

    orders = await fetch_all_orders()

    new_orders: list[dict] = []
    matched_count = 0

    for order in orders:
        order_id = order.get("id")

        if not order_id:
            continue

        if is_seen(order_id):
            continue

        if not _matches_keywords(order):
            continue

        matched_count += 1
        new_orders.append(order)

    logger.info(
        "Найдено %d заказов, из них %d содержат ключевые слова",
        len(orders),
        matched_count,
    )

    logger.info(
        "Парсинг завершён. "
        "Всего найдено карточек: %d, новых (с учётом ключевых слов): %d",
        len(orders),
        len(new_orders),
    )

    return new_orders
