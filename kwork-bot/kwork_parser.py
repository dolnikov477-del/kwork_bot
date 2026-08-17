"""
Парсер заказов Kwork через Playwright + BeautifulSoup.

Логика:
- при первом запуске текущие заказы сохраняются в базу и НЕ отправляются;
- после первого запуска отправляются только действительно новые заказы;
- фильтрация идёт только по выбранным категориям Kwork;
- ключевые слова не используются.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page, async_playwright

from config import settings
from storage import is_seen, save_order

logger = logging.getLogger(__name__)

KWORK_BASE_URL = "https://kwork.ru/projects"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_ID_RE = re.compile(r"/projects/(\d+)")


def _parse_orders_from_html(html: str) -> list[dict]:
    """Извлекает заказы из HTML страницы Kwork."""

    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select(".wants-card")

    orders: list[dict] = []

    for card in cards:
        link = card.select_one(
            ".wants-card__header-title a[href*='/projects/']"
        )

        if link is None:
            link = card.select_one("a[href*='/projects/']")

        if link is None:
            continue

        href = link.get("href")

        if not href:
            continue

        id_match = _ID_RE.search(href)

        if not id_match:
            continue

        order_id = id_match.group(1)

        title_el = card.select_one(".wants-card__header-title")

        if title_el:
            title = title_el.get_text(" ", strip=True)
        else:
            title = link.get_text(" ", strip=True)

        description_el = card.select_one(
            ".wants-card__description-text"
        )

        description = (
            description_el.get_text(" ", strip=True)
            if description_el
            else ""
        )

        price_el = card.select_one(".wants-card__right")

        price = (
            price_el.get_text(" ", strip=True)
            if price_el
            else ""
        )

        if href.startswith("http"):
            url = href
        else:
            url = f"https://kwork.ru{href}"

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


async def fetch_orders_for_category(
    page: Page,
    category_id: str,
) -> list[dict]:
    """Загружает заказы конкретной категории."""

    url = f"{KWORK_BASE_URL}?fc={category_id}"

    logger.info(
        "Открываем категорию %s: %s",
        category_id,
        url,
    )

    try:
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        status = response.status if response else None

        logger.info(
            "Категория %s: HTTP статус: %s",
            category_id,
            status,
        )

        logger.info(
            "Категория %s: финальный URL: %s",
            category_id,
            page.url,
        )

        title = await page.title()

        logger.info(
            "Категория %s: title: %s",
            category_id,
            title,
        )

        # Даём JavaScript Kwork время отрисовать карточки.
        await page.wait_for_timeout(3000)

        # Ждём появления карточек, но не падаем,
        # если их пока нет.
        try:
            await page.wait_for_selector(
                ".wants-card",
                timeout=10000,
            )
        except Exception:
            logger.warning(
                "Категория %s: .wants-card не появился за 10 секунд",
                category_id,
            )

        # Небольшое ожидание после появления карточек.
        await page.wait_for_timeout(1000)

        html = await page.content()

        # --- Диагностика содержимого страницы ---
        # Помогает понять, получает ли Playwright реальный
        # HTML с карточками, или пустой SSR-шаблон / блокировку.

        logger.info(
            "Категория %s: [DIAG] длина HTML: %d",
            category_id,
            len(html),
        )

        logger.info(
            "Категория %s: [DIAG] 'wants-card' в HTML (текст): %s",
            category_id,
            "wants-card" in html,
        )

        logger.info(
            "Категория %s: [DIAG] 'заказ' в HTML: %s",
            category_id,
            "заказ" in html.lower(),
        )

        logger.info(
            "Категория %s: [DIAG] другие русские слова "
            "('проект', 'категор', 'бюджет') в HTML: %s / %s / %s",
            category_id,
            "проект" in html.lower(),
            "категор" in html.lower(),
            "бюджет" in html.lower(),
        )

        logger.info(
            "Категория %s: [DIAG] 'body' в HTML: %s",
            category_id,
            "body" in html.lower(),
        )

        logger.info(
            "Категория %s: [DIAG] первые 1000 символов HTML:\n%s",
            category_id,
            html[:1000],
        )

        diag_soup = BeautifulSoup(html, "html.parser")

        diag_div_count = len(diag_soup.find_all("div"))

        logger.info(
            "Категория %s: [DIAG] всего div-элементов в HTML: %d",
            category_id,
            diag_div_count,
        )

        diag_wants_card_count = len(diag_soup.select(".wants-card"))

        logger.info(
            "Категория %s: [DIAG] .wants-card через селектор: %d "
            "(текст 'wants-card' в HTML: %s)",
            category_id,
            diag_wants_card_count,
            "wants-card" in html,
        )

        for marker in (
            "no orders",
            "nothing found",
            "error",
            "not found",
            "access denied",
            "captcha",
            "ничего не найдено",
            "нет заказов",
        ):
            logger.info(
                "Категория %s: [DIAG] маркер '%s' в HTML: %s",
                category_id,
                marker,
                marker in html.lower(),
            )

        # --- Конец диагностики ---

        orders = _parse_orders_from_html(html)

        logger.info(
            "Категория %s: найдено карточек: %d",
            category_id,
            len(orders),
        )

        return orders

    except Exception as e:
        logger.error(
            "Категория %s: ошибка загрузки: %s",
            category_id,
            e,
        )

        return []


async def fetch_all_orders() -> list[dict]:
    """
    Получает заказы из всех настроенных категорий.
    """

    all_orders: list[dict] = []

    async with async_playwright() as playwright:

        browser: Browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        try:
            context = await browser.new_context(
                user_agent=_USER_AGENT,
                locale="ru-RU",
                viewport={
                    "width": 1920,
                    "height": 1080,
                },
            )

            page: Page = await context.new_page()

            # Сначала открываем главную страницу.
            # Это помогает получить базовые cookies Kwork.
            try:
                logger.info("Открываем главную страницу Kwork...")

                await page.goto(
                    "https://kwork.ru/",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                await page.wait_for_timeout(2000)

                logger.info(
                    "Главная страница открыта. URL: %s",
                    page.url,
                )

            except Exception as e:
                logger.warning(
                    "Не удалось открыть главную страницу Kwork: %s",
                    e,
                )

            # Обходим все категории.
            for category_id in settings.KWORK_CATEGORY_IDS:

                try:
                    orders = await fetch_orders_for_category(
                        page,
                        category_id,
                    )

                    all_orders.extend(orders)

                except Exception as e:
                    logger.error(
                        "Ошибка категории %s: %s",
                        category_id,
                        e,
                    )

            await context.close()

        finally:
            await browser.close()

    # Убираем дубликаты.
    unique_orders: dict[str, dict] = {}

    for order in all_orders:

        order_id = order.get("id")

        if order_id:
            unique_orders[order_id] = order

    result = list(unique_orders.values())

    logger.info(
        "Всего уникальных заказов после обхода категорий: %d",
        len(result),
    )

    return result


async def initialize_seen_orders() -> int:
    """
    Первичная инициализация.

    Все заказы, которые существуют на момент запуска,
    записываются в базу.

    В Telegram они НЕ отправляются.
    """

    logger.info(
        "========================================"
    )

    logger.info(
        "ПЕРВЫЙ ЗАПУСК: запоминаем существующие заказы"
    )

    logger.info(
        "========================================"
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
        "Первичная инициализация завершена."
    )

    logger.info(
        "Сохранено существующих заказов: %d",
        added,
    )

    return added


async def fetch_new_orders() -> list[dict]:
    """
    Возвращает только новые заказы.

    Ключевые слова НЕ используются.

    Новый заказ определяется исключительно по ID:
    если ID нет в базе — заказ новый.
    """

    logger.info(
        "========================================"
    )

    logger.info(
        "Начинаем проверку новых заказов"
    )

    logger.info(
        "========================================"
    )

    orders = await fetch_all_orders()

    new_orders: list[dict] = []

    for order in orders:

        order_id = order.get("id")

        if not order_id:
            continue

        # Уже видели — пропускаем.
        if is_seen(order_id):
            continue

        # Новый заказ.
        new_orders.append(order)

    logger.info(
        "Всего найдено заказов: %d",
        len(orders),
    )

    logger.info(
        "Новых заказов: %d",
        len(new_orders),
    )

    for order in new_orders:

        logger.info(
            "НОВЫЙ ЗАКАЗ: ID=%s | %s",
            order["id"],
            order.get("title", ""),
        )

    return new_orders
