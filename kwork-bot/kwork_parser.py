"""
Парсер биржи заказов Kwork через headless-браузер (Playwright).
"""

from __future__ import annotations

import asyncio
import logging
import time

from playwright.async_api import async_playwright

from config import settings

logger = logging.getLogger(__name__)

KWORK_BASE_URL = "https://kwork.ru/projects"

# Таймаут на загрузку одной страницы категории (в миллисекундах / секундах)
PAGE_TIMEOUT_MS = 10_000
PAGE_TIMEOUT_SEC = PAGE_TIMEOUT_MS / 1000

# Максимальное время на весь цикл парсинга всех категорий (в секундах)
FULL_PARSE_TIMEOUT_SEC = 60

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
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        await asyncio.wait_for(page.wait_for_timeout(1500), timeout=PAGE_TIMEOUT_SEC)
    except asyncio.TimeoutError as e:
        logger.error(
            "Таймаут (%.0fс) при загрузке страницы категории %s: %s",
            PAGE_TIMEOUT_SEC,
            category_id,
            e,
        )
        raise
    except Exception as e:
        logger.error(
            "Ошибка при загрузке страницы категории %s: %s", category_id, e
        )
        raise
    return await page.evaluate(_EXTRACT_JS)

async def fetch_new_orders() -> list[dict]:
    """Собирает заказы по всем настроенным категориям и фильтрует по ключевым словам.

    Вся операция ограничена таймаутом FULL_PARSE_TIMEOUT_SEC. Если парсинг
    не укладывается в это время (например, браузер завис), задача
    принудительно отменяется и возвращается пустой список.
    """
    started_at = time.monotonic()
    logger.info("Парсинг заказов начат")

    try:
        result = await asyncio.wait_for(
            _fetch_new_orders_impl(), timeout=FULL_PARSE_TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - started_at
        logger.warning(
            "Парсинг таймаутился (превышен лимит %.0fс, прошло %.1fс)",
            FULL_PARSE_TIMEOUT_SEC,
            elapsed,
        )
        return []
    except Exception as e:
        elapsed = time.monotonic() - started_at
        logger.error("Парсинг завершился с ошибкой за %.1fс: %s", elapsed, e)
        return []

    elapsed = time.monotonic() - started_at
    logger.info("Парсинг заказов завершён за %.1fс, найдено новых: %d", elapsed, len(result))
    return result


async def _fetch_new_orders_impl() -> list[dict]:
    """Внутренняя реализация сбора заказов (без таймаута верхнего уровня)."""
    from storage import is_seen

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

        for category_id in settings.KWORK_CATEGORY_IDS:
            try:
                orders = await fetch_orders_for_category(page, category_id)
            except Exception as e:
                logger.error("Ошибка при обходе категории %s: %s", category_id, e)
                continue

            for order in orders:
                if not order.get("id") or is_seen(order["id"]):
                    continue

                if settings.KEYWORDS:
                    text = f"{order.get('title', '')} {order.get('description', '')}".lower()
                    if not any(kw.lower() in text for kw in settings.KEYWORDS):
                        continue

                all_new.append(order)

        await browser.close()

    return all_new