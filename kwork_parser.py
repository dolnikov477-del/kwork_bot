"""
Парсер заказов Kwork через Playwright.
"""

from __future__ import annotations

import logging
from playwright.async_api import async_playwright

from config import settings
from storage import is_seen, save_order, has_any_seen

logger = logging.getLogger(__name__)

KWORK_BASE_URL = "https://kwork.ru/projects"

_EXTRACT_JS = """
() => {
    const cards = Array.from(document.querySelectorAll('.want-card'));

    return cards.map(card => {
        const link = card.querySelector('.wants-card__header-title a[href*="/projects/"]');
        const href = link ? link.getAttribute('href') : null;

        const idMatch = href ? href.match(/projects\\/(\\d+)/) : null;

        const title = link?.innerText?.trim() || '';
        const description =
            card.querySelector('.wants-card__description-text')?.innerText?.trim() || '';

        const price =
            card.querySelector('.wants-card__right')?.innerText?.trim() || '';

        return {
            id: idMatch ? idMatch[1] : href,
            title,
            description,
            price,
            url: href
                ? (href.startsWith('http') ? href : 'https://kwork.ru' + href)
                : null,
        };
    }).filter(c => c.title && c.id);
}
"""


async def fetch_orders_for_category(page, category_id: str) -> list[dict]:
    url = f"{KWORK_BASE_URL}?fc={category_id}"

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=30000,
    )

    await page.wait_for_timeout(1500)

    return await page.evaluate(_EXTRACT_JS)


async def fetch_new_orders() -> list[dict]:
    """
    Получает заказы из настроенных категорий.

    Первый запуск:
        существующие заказы только запоминаются.

    Последующие запуски:
        возвращаются только действительно новые заказы.
    """

    all_new: list[dict] = []

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

        first_run = not has_any_seen()

        for category_id in settings.KWORK_CATEGORY_IDS:

            try:
                orders = await fetch_orders_for_category(
                    page,
                    category_id,
                )

                logger.info(
                    "Категория %s: найдено заказов: %s",
                    category_id,
                    len(orders),
                )

            except Exception as e:
                logger.exception(
                    "Ошибка при обходе категории %s: %s",
                    category_id,
                    e,
                )
                continue

            for order in orders:

                order_id = order.get("id")

                if not order_id:
                    continue

                # Уже видели этот заказ
                if is_seen(order_id):
                    continue

                # Первый запуск:
                # НЕ отправляем старые заказы,
                # просто сохраняем их.
                if first_run:
                    save_order(order)
                    continue

                # Новый заказ
                save_order(order)
                all_new.append(order)

        await browser.close()

    logger.info(
        "Парсинг завершён. Новых заказов: %s",
        len(all_new),
    )

    return all_new