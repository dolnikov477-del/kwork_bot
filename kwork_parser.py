"""
Парсер заказов Kwork через Playwright.
"""

from __future__ import annotations

import asyncio
import logging
import re
import random
from datetime import datetime, timezone
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config import settings
from storage import is_seen

logger = logging.getLogger(__name__)

KWORK_BASE_URL = "https://kwork.ru/projects"

# Rotate user agents to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


def _parse_replies_count(text: str) -> int:
    if not text:
        return 0
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def _is_too_old(published_at: str, max_age_hours: int = settings.MAX_AGE_HOURS) -> bool:
    if not published_at:
        return False
    try:
        # Handle various ISO format variations
        normalized = published_at.replace("Z", "+00:00")
        if "+00:00" not in normalized and "Z" not in normalized:
            normalized += "+00:00"  # Assume UTC if no timezone
        dt = datetime.fromisoformat(normalized)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() > max_age_hours * 3600
    except Exception as e:
        logger.debug("Не удалось распарсить дату '%s': %s", published_at, e)
        return False  # If we can't parse date, don't filter by age


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

        const repliesText =
            card.querySelector('.wants-card__footer-item')?.innerText?.trim() || '';

        const publishedAt =
            card.querySelector('time')?.getAttribute('datetime') || '';

        return {
            id: idMatch ? idMatch[1] : href,
            title,
            description,
            price,
            url: href
                ? (href.startsWith('http') ? href : 'https://kwork.ru' + href)
                : null,
            repliesText,
            publishedAt,
        };
    }).filter(c => c.title && c.id);
}
"""

async def fetch_orders_for_category(page, category_id: str) -> list[dict]:
    """Переходит на страницу категории в уже открытой вкладке и возвращает заказы."""
    url = f"{KWORK_BASE_URL}?fc={category_id}"
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(1500)
    orders = await page.evaluate(_EXTRACT_JS)

    if not orders:
        title = await page.title()
        body_snippet = await page.evaluate("() => document.body.innerText.slice(0, 300)")
        card_count_raw = await page.evaluate("() => document.querySelectorAll('.want-card').length")
        print(
            f"[parser][debug] fc={category_id} | title='{title}' | "
            f".want-card найдено сырых: {card_count_raw} | "
            f"начало текста страницы: {body_snippet!r}"
        )

    return orders


async def fetch_new_orders() -> list[dict]:
    """
    Получает заказы из настроенных категорий и возвращает список новых заказов.
    """
    new_orders: list[dict] = []

    async with async_playwright() as p:
        browser = None
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

            user_agent = random.choice(USER_AGENTS)
            page = await browser.new_page(user_agent=user_agent)

            logger.info("Категории для парсинга: %s", settings.KWORK_CATEGORY_IDS)

            for category_id in settings.KWORK_CATEGORY_IDS:
                try:
                    orders = await fetch_orders_for_category(page, category_id)

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
                    await asyncio.sleep(5)
                    continue

                sent_in_category = 0

                for order in orders:
                    order_id = order.get("id")

                    if not order_id:
                        continue

                    if is_seen(order_id):
                        logger.debug("Пропуск заказа %s: уже отправлен", order_id)
                        continue

                    replies_count = _parse_replies_count(order.get("repliesText", ""))
                    if replies_count > settings.MAX_REPLIES:
                        logger.info(
                            "Пропуск заказа %s: откликов %d > %d",
                            order_id,
                            replies_count,
                            settings.MAX_REPLIES,
                        )
                        continue

                    if _is_too_old(order.get("publishedAt", "")):
                        logger.info(
                            "Пропуск заказа %s: заказ старше %d часов",
                            order_id,
                            settings.MAX_AGE_HOURS,
                        )
                        continue

                    new_orders.append(order)
                    sent_in_category += 1
                    if sent_in_category >= settings.MAX_ORDERS_PER_CATEGORY:
                        logger.info(
                            "Достигнут лимит заказов для категории %s: %d",
                            category_id,
                            settings.MAX_ORDERS_PER_CATEGORY,
                        )
                        break

                await asyncio.sleep(8 + random.uniform(0, 4))

        except Exception as e:
            logger.exception("Критическая ошибка в парсере: %s", e)
            raise
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    logger.error("Ошибка при закрытии браузера: %s", e)

    return new_orders