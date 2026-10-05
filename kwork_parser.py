"""
Парсер заказов Kwork через Playwright.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import signal
from datetime import datetime, timezone
from typing import AsyncGenerator

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config import settings
from storage import is_seen

logger = logging.getLogger(__name__)

KWORK_BASE_URL = "https://kwork.ru/projects"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# Настройки защиты от блокировок
BLOCK_DETECTION_TITLE = "Доступ заблокирован"
BLOCK_DETECTION_SELECTORS = [
    "text=Доступ заблокирован",
    ".captcha",
    "[data-testid='captcha']",
    "#challenge-form",
    ".cf-challenge-running",
]
MAX_BLOCK_RETRIES = 3
BLOCK_RETRY_DELAY_BASE = 60  # базовая задержка в секундах при блокировке
BLOCK_RETRY_DELAY_MAX = 300  # максимальная задержка в секундах

_shutdown_event = asyncio.Event()


def _parse_replies_count(text: str) -> int:
    if not text:
        return 0
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def _is_too_old(published_at: str, max_age_hours: float = settings.MAX_AGE_HOURS) -> bool:
    if not published_at:
        return False
    try:
        normalized = published_at.replace("Z", "+00:00")
        if "+00:00" not in normalized and "Z" not in normalized:
            normalized += "+00:00"
        dt = datetime.fromisoformat(normalized)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() > max_age_hours * 3600
    except Exception as e:
        logger.debug("Не удалось распарсить дату '%s': %s", published_at, e)
        return False


async def _is_blocked(page) -> bool:
    """Проверяет, заблокирован ли доступ (капча, страница блокировки и т.д.)."""
    try:
        title = await page.title()
        if BLOCK_DETECTION_TITLE in title:
            return True
        
        content = await page.content()
        if BLOCK_DETECTION_TITLE in content:
            return True
            
        for selector in BLOCK_DETECTION_SELECTORS:
            try:
                if await page.query_selector(selector):
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


async def _handle_block(page, category_id: str, attempt: int) -> bool:
    """
    Обрабатывает обнаруженную блокировку.
    Возвращает True, если стоит повторить попытку, False — если прерывать.
    """
    logger.warning(
        "[parser][block] Обнаружена блокировка для категории %s (попытка %d/%d)",
        category_id, attempt, MAX_BLOCK_RETRIES
    )
    
    # Уведомление администратора (заглушка — можно интегрировать с ботом)
    logger.critical(
        "[parser][ALERT] Блокировка на категории %s! Требуется вмешательство администратора.",
        category_id
    )
    
    if attempt >= MAX_BLOCK_RETRIES:
        logger.error("[parser][block] Превышено макс. число попыток (%d) для категории %s", MAX_BLOCK_RETRIES, category_id)
        return False
    
    # Экспоненциальная задержка с джиттером
    delay = min(BLOCK_RETRY_DELAY_BASE * (2 ** (attempt - 1)) + random.uniform(0, 10), BLOCK_RETRY_DELAY_MAX)
    logger.info("[parser][block] Пауза %.1f сек перед повтором...", delay)
    await asyncio.sleep(delay)
    
    # Пробуем обновить страницу с новым User-Agent
    try:
        new_ua = random.choice(USER_AGENTS)
        await page.set_extra_http_headers({"User-Agent": new_ua})
        await page.reload(wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        logger.warning("[parser][block] Ошибка при смене UA/перезагрузке: %s", e)
    
    return True


# Улучшенный JS с множественными fallback селекторами
_EXTRACT_JS = """
() => {
    // Множественные селекторы для карточек
    const cardSelectors = [
        '.want-card',
        '.card',
        '[data-want-id]',
        '.project-card',
        '.order-card',
        '.wants-card',
        '.js-want-card',
        '.js-project-card',
        '.project-item',
        '.order-item',
        '.task-card'
    ];
    
    let cards = [];
    for (const sel of cardSelectors) {
        const found = Array.from(document.querySelectorAll(sel));
        if (found.length > 0) {
            cards = found;
            break;
        }
    }
    if (cards.length === 0) {
        // Фоллбек: ищем любые ссылки на /projects/
        const links = Array.from(document.querySelectorAll('a[href*="/projects/"]'));
        cards = links.map(l => l.closest('div, article, section, li') || l.parentElement).filter(Boolean);
    }

    return cards.map(card => {
        // Пробуем разные селекторы для ссылки
        let link = card.querySelector('.wants-card__header-title a[href*="/projects/"]');
        if (!link) link = card.querySelector('a[href*="/projects/"]');
        if (!link) link = card.querySelector('h3 a, h4 a, .title a, .name a');
        const href = link ? link.getAttribute('href') : null;

        const idMatch = href ? href.match(/projects\\/(\\d+)/) : null;

        // Заголовок
        let title = '';
        if (link) title = link.innerText?.trim() || '';
        if (!title) {
            const titleEl = card.querySelector('h3, h4, .title, .name, .wants-card__header-title, [class*="title"]');
            title = titleEl?.innerText?.trim() || '';
        }

        // Описание - пробуем разные селекторы
        let description = '';
        const descSelectors = [
            '.wants-card__description-text',
            '.description',
            '.description-text',
            '[class*="description"]',
            'p'
        ];
        for (const sel of descSelectors) {
            const el = card.querySelector(sel);
            if (el && el.innerText?.trim()) {
                description = el.innerText.trim();
                break;
            }
        }

        // Цена
        let price = '';
        const priceSelectors = [
            '.wants-card__right',
            '.price',
            '.cost',
            '[class*="price"]',
            '[class*="cost"]'
        ];
        for (const sel of priceSelectors) {
            const el = card.querySelector(sel);
            if (el && el.innerText?.trim()) {
                price = el.innerText.trim();
                break;
            }
        }

        // Отклики - ищем в тексте карточки
        let repliesText = '';
        const allText = card.innerText || '';
        const repliesMatch = allText.match(/Предложений\\s*:?\\s*(\\d+)/);
        if (repliesMatch) {
            repliesText = 'Предложений: ' + repliesMatch[1];
        } else {
            const spans = card.querySelectorAll('span, div, p');
            for (const span of spans) {
                const txt = span.innerText || '';
                if (txt.includes('Предложений')) {
                    repliesText = txt.trim();
                    break;
                }
            }
        }

        // Дата
        let publishedAt = '';
        const timeEl = card.querySelector('time');
        if (timeEl) {
            publishedAt = timeEl.getAttribute('datetime') || timeEl.getAttribute('title') || '';
        }
        if (!publishedAt) {
            const timeMatch = allText.match(/(\\d{1,2}\\.\\d{1,2}\\.\\d{4})/);
            if (timeMatch) publishedAt = timeMatch[1];
        }

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


async def _fetch_orders_for_category(page, category_id: str) -> list[dict]:
    """Переходит на страницу категории и возвращает заказы."""
    url = f"{KWORK_BASE_URL}?fc={category_id}"
    logger.info("[parser] Перехожу на URL: %s", url)

    timeout = getattr(settings, 'PAGE_LOAD_TIMEOUT', 60000)

    for attempt in range(1, 4):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            
            # Проверка на блокировку сразу после загрузки
            if await _is_blocked(page):
                if not await _handle_block(page, category_id, attempt):
                    return []
                continue
            
            # Ждём загрузки страницы (не обязательно наличие карточек)
            await page.wait_for_timeout(3000)
            
            # Проверяем есть ли на странице карточки (быстрая проверка)
            has_cards = await page.evaluate("""
                () => {
                    const selectors = ['.want-card', '.card', '[data-want-id]', '.project-card', '.order-card', '.wants-card', '.js-want-card', '.project-item', '.order-item', '.task-card', 'a[href*="/projects/"]'];
                    for (const sel of selectors) {
                        if (document.querySelectorAll(sel).length > 0) return true;
                    }
                    return false;
                }
            """)
            
            if not has_cards:
                title = await page.title()
                html_len = await page.evaluate("() => document.body.innerHTML.length")
                logger.warning(
                    "[parser] Категория %s: карточки не найдены (попытка %d). Title=%s, body_len=%d",
                    category_id, attempt, title, html_len
                )
                if attempt < 3:
                    # Пробуем перезагрузить с другим User-Agent
                    new_ua = random.choice(USER_AGENTS)
                    await page.set_extra_http_headers({"User-Agent": new_ua})
                    await page.reload(wait_until="domcontentloaded", timeout=timeout)
                    await page.wait_for_timeout(5000)
                    continue
                else:
                    return []
            
            break
        except PlaywrightTimeoutError:
            logger.warning("[parser] Таймаут загрузки категории %s (попытка %d/3)", category_id, attempt)
            if attempt < 3:
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=timeout)
                    await page.wait_for_timeout(5000)
                except Exception:
                    pass
                continue
            else:
                logger.error("[parser] Таймаут загрузки категории %s после 3 попыток", category_id)
                try:
                    html = await page.content()
                    title = await page.title()
                    logger.error("[parser][debug] HTML category %s | title: %s | len: %d", category_id, title, len(html))
                except Exception:
                    pass
                return []
        except Exception as e:
            logger.exception("[parser] Ошибка при переходе на категорию %s: %s", category_id, e)
            return []

    logger.info("[parser] Ищу карточки заказов на странице категории %s...", category_id)
    
    # Проверка на блокировку перед парсингом
    if await _is_blocked(page):
        if not await _handle_block(page, category_id, 1):
            return []

    # Пробуем разные селекторы для подсчёта карточек
    card_count_raw = await page.evaluate("""
        () => {
            const selectors = ['.want-card', '.card', '[data-want-id]', '.project-card', '.order-card', '.wants-card', '.js-want-card', '.project-item', '.order-item', '.task-card'];
            for (const sel of selectors) {
                const found = document.querySelectorAll(sel);
                if (found.length > 0) return found.length;
            }
            return 0;
        }
    """)
    logger.info("[parser] Категория %s: найдено сырых карточек: %d", category_id, card_count_raw)

    if card_count_raw == 0:
        try:
            html = await page.content()
            title = await page.title()
            logger.warning("[parser] Категория %s: 0 карточек. Title: %s. HTML (first 5000): %s",
                          category_id, title, html[:5000])
        except Exception:
            pass
        return []

    orders = await page.evaluate(_EXTRACT_JS)

    logger.info("[parser] Категория %s: распарсено заказов: %d", category_id, len(orders))
    for o in orders:
        _rc = _parse_replies_count(o.get('repliesText', ''))
        logger.info(
            "[parser] Заказ %s | title=%s | repliesText=%r | replies_count=%d | publishedAt=%r",
            o.get('id'), o.get('title', '')[:50], o.get('repliesText', ''), _rc, o.get('publishedAt', '')
        )

    if not orders:
        try:
            html = await page.content()
            title = await page.title()
            logger.warning("[parser] Категория %s: 0 заказов после парсинга. Title: %s. HTML (first 5000): %s",
                          category_id, title, html[:5000])
        except Exception:
            pass

    return orders


async def fetch_new_orders() -> AsyncGenerator[dict, None]:
    """
    Асинхронный генератор: выдаёт новые заказы по мере обнаружения.
    Проходит категории последовательно, внутри категории — по заказам.
    Фильтрует старые, забитые и уже отправленные заказы на лету.
    """
    _shutdown_event.clear()
    
    def _signal_handler():
        logger.info("Получен сигнал завершения, останавливаю парсер...")
        _shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    async with async_playwright() as p:
        browser = None

        async def ensure_browser() -> bool:
            nonlocal browser
            if browser is None or not browser.is_connected():
                logger.warning("Браузер отключен или не запущен, пытаюсь перезапустить...")
                try:
                    if browser:
                        await browser.close()
                except Exception:
                    pass
                browser = None
                for attempt in range(1, 4):
                    try:
                        browser = await p.chromium.launch(
                            headless=True,
                            args=[
                                "--disable-dev-shm-usage",
                                "--no-sandbox",
                                "--disable-setuid-sandbox",
                                "--disable-gpu",
                                "--disable-extensions",
                                "--disable-background-networking",
                                "--disable-background-timer-throttling",
                                "--disable-backgrounding-occluded-windows",
                                "--disable-renderer-backgrounding",
                                "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                                "--memory-pressure-off",
                                "--max_old_space_size=256",
                            ],
                            env={
                                "XDG_CONFIG_HOME": "/tmp",
                                "XDG_CACHE_HOME": "/tmp",
                            },
                        )
                        logger.info("Браузер успешно запущен (попытка %d)", attempt)
                        return True
                    except Exception as e:
                        logger.error("Не удалось запустить браузер (попытка %d/3): %s", attempt, e)
                        if attempt < 3:
                            await asyncio.sleep(5.0)
                logger.error("Не удалось запустить браузер после 3 попыток")
                return False
            return True

        if not await ensure_browser():
            return

        try:
            for category_id in settings.KWORK_CATEGORY_IDS:
                if _shutdown_event.is_set():
                    logger.info("Завершение по сигналу, прерываю парсинг")
                    break

                page = None
                try:
                    if not await ensure_browser():
                        break

                    user_agent = random.choice(USER_AGENTS)
                    page = await browser.new_page(user_agent=user_agent)
                    page.set_default_timeout(30000)

                    try:
                        orders = await _fetch_orders_for_category(page, category_id)
                    except Exception as e:
                        logger.exception("Ошибка при обходе категории %s: %s", category_id, e)
                        await asyncio.sleep(5)
                        continue

                    sent_in_category = 0

                    for order in orders:
                        if _shutdown_event.is_set():
                            break
                        order_id = order.get("id")
                        if not order_id:
                            continue

                        if is_seen(order_id):
                            logger.debug("Пропуск заказа %s: уже отправлен", order_id)
                            continue

                        replies_count = _parse_replies_count(order.get("repliesText", ""))
                        logger.info(
                            "[parser] Обработка заказа %s: replies_count=%d (repliesText=%r)",
                            order_id, replies_count, order.get("repliesText", "")
                        )
                        if replies_count > settings.MAX_REPLIES:
                            logger.info(
                                "Пропуск заказа %s: откликов %d > %d",
                                order_id, replies_count, settings.MAX_REPLIES
                            )
                            continue

                        if _is_too_old(order.get("publishedAt", "")):
                            logger.info(
                                "Пропуск заказа %s: заказ старше %.1f часов",
                                order_id, settings.MAX_AGE_HOURS
                            )
                            continue

                        if sent_in_category >= settings.MAX_ORDERS_PER_CATEGORY:
                            logger.info(
                                "Достигнут лимит заказов для категории %s: %d",
                                category_id, settings.MAX_ORDERS_PER_CATEGORY
                            )
                            break

                        sent_in_category += 1
                        yield order

                except Exception as e:
                    logger.exception("Критическая ошибка в парсере для категории %s: %s", category_id, e)
                finally:
                    if page:
                        try:
                            await page.close()
                        except Exception as e:
                            logger.error("Ошибка при закрытии страницы: %s", e)

                # Рандомная задержка между категориями для имитации человека
                delay = 3 + random.uniform(0, 5)
                logger.debug("[parser] Пауза %.1f сек перед следующей категорией...", delay)
                await asyncio.sleep(delay)
        finally:
            if browser:
                try:
                    await browser.close()
                    logger.info("Браузер закрыт корректно")
                except Exception as e:
                    logger.error("Ошибка при закрытии браузера: %s", e)