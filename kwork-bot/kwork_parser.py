"""
Парсер биржи заказов Kwork через headless-браузер (Playwright).
"""

from __future__ import annotations

import logging

from playwright.async_api import async_playwright

from config import settings

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
        const description = card.querySelector('.wants-card__description-text')?.innerText?.trim() || '';
        const price = card.querySelector('.wants-card__right')?.innerText?.trim() || '';
        return {
            id: idMatch ? idMatch[1] : href,
            title,
            description,
            price,
            url: href ? (href.startsWith('http') ? href : 'https://kwork.ru' + href) : null,
        };
    }).filter(c => c.title && c.id);
}
"""

async def fetch_orders_for_category(page, category_id: str) -> list[dict]:
    """Переходит на страницу категории в уже открытой вкладке и возвращает заказы."""
    url = f"{KWORK_BASE_URL}?fc={category_id}"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)
    return await page.evaluate(_EXTRACT_JS)

async def fetch_new_orders() -> list[dict]:
    """Собирает заказы по всем настроенным категориям и фильтрует по ключевым словам."""
    from storage import is_seen

    logger.info("Парсинг начался")

    all_new: list[dict] = []

    try:
        async with async_playwright() as p:
            try:
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
            except Exception as e:
                logger.error("Не удалось запустить браузер Playwright: %s", e)
                return []

            try:
                page = await browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )

                for category_id in settings.KWORK_CATEGORY_IDS:
                    try:
                        orders = await fetch_orders_for_category(page, category_id)
                    except Exception as e:
                        logger.error(
                            "Ошибка при обходе категории %s: %s", category_id, e
                        )
                        continue

                    for order in orders:
                        if not order.get("id") or is_seen(order["id"]):
                            continue

                        if settings.KEYWORDS:
                            text = f"{order.get('title', '')} {order.get('description', '')}".lower()
                            if not any(kw.lower() in text for kw in settings.KEYWORDS):
                                continue

                        all_new.append(order)
            finally:
                try:
                    await browser.close()
                except Exception as e:
                    logger.error("Ошибка при закрытии браузера Playwright: %s", e)
    except Exception as e:
        logger.error("Ошибка Playwright в fetch_new_orders: %s", e)
        return []

    logger.info("Парсинг закончился, найдено %d заказов", len(all_new))

    return all_new