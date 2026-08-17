"""
Парсер заказов Kwork через Playwright.

Логика:
- при первом запуске запоминает все уже существующие заказы;
- старые заказы НЕ отправляет;
- после этого отправляет только заказы, которых раньше не видел.
"""

from __future__ import annotations

import logging

from playwright.async_api import async_playwright

from config import settings
from storage import is_seen, save_order

logger = logging.getLogger(__name__)

KWORK_BASE_URL = "https://kwork.ru/projects"

_EXTRACT_JS = """
() => {
    const cards = Array.from(document.querySelectorAll('.want-card'));

    return cards.map(card => {
        const link = card.querySelector(
            '.wants-card__header-title a[href*="/projects/"]'
        );

        const href = link
            ? link.getAttribute('href')
            : null;

        const idMatch = href
            ? href.match(/projects\\/(\\d+)/)
            : null;

        const title = link?.innerText?.trim() || '';

        const description =
            card.querySelector(
                '.wants-card__description-text'
            )?.innerText?.trim() || '';

        const price =
            card.querySelector(
                '.wants-card__right'
            )?.innerText?.trim() || '';

        return {
            id: idMatch ? idMatch[1] : href,
            title,
            description,
            price,
            url: href
                ? (
                    href.startsWith('http')
                        ? href
                        : 'https://kwork.ru' + href
                )
                : null,
        };
    }).filter(order => order.title && order.id);
}
"""


async def fetch_orders_for_category(
    page,
    category_id: str,
) -> list[dict]:
    """
    Получает заказы одной категории.
    """

    url = f"{KWORK_BASE_URL}?fc={category_id}"

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=30000,
    )

    await page.wait_for_timeout(1500)

    orders = await page.evaluate(_EXTRACT_JS)

    logger.info(
        "Категория %s: найдено карточек: %d",
        category_id,
        len(orders),
    )

    return orders


async def fetch_all_orders() -> list[dict]:
    """
    Получает все заказы из всех настроенных категорий.
    """

    all_orders: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--ignore-certificate-errors",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        try:
            for category_id in settings.KWORK_CATEGORY_IDS:
                try:
                    orders = await fetch_orders_for_category(
                        page,
                        category_id,
                    )

                    all_orders.extend(orders)

                except Exception as e:
                    logger.error(
                        "Ошибка при обходе категории %s: %s",
                        category_id,
                        e,
                    )

        finally:
            await browser.close()

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


async def fetch_new_orders() -> list[dict]:
    """
    Получает только новые заказы.

    Заказ считается новым, если его ID ещё нет
    в базе просмотренных заказов.
    """

    logger.info("Парсинг заказов начат")

    orders = await fetch_all_orders()

    new_orders: list[dict] = []

    for order in orders:
        order_id = order.get("id")

        if not order_id:
            continue

        if is_seen(order_id):
            continue

        new_orders.append(order)

    logger.info(
        "Парсинг завершён. "
        "Всего найдено карточек: %d, новых: %d",
        len(orders),
        len(new_orders),
    )

    return new_orders
