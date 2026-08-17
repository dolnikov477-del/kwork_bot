import asyncio
import logging
from functools import wraps

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ai_responder import generate_reply
from config import settings
from kwork_parser import fetch_new_orders
from storage import get_order, init_db, save_order

logger = logging.getLogger(__name__)


def retry_on_network_error(max_retries: int = 3, delay: float = 2.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None

            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except (TelegramNetworkError, OSError, ConnectionError) as e:
                    last_exc = e

                    logger.warning(
                        "Сетевая ошибка (попытка %d/%d): %s",
                        attempt,
                        max_retries,
                        e,
                    )

                    if attempt < max_retries:
                        await asyncio.sleep(delay * attempt)

            raise last_exc

        return wrapper

    return decorator


bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()


def _order_keyboard(order_id: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Перейти к заказу",
                    url=url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="✨ Сгенерировать отклик",
                    callback_data=f"gen:{order_id}",
                )
            ],
        ]
    )


def _format_order_message(order: dict) -> str:
    price_line = (
        f"\n💰 Бюджет: {order['price']}"
        if order.get("price")
        else ""
    )

    description = order.get("description", "")

    if len(description) > 500:
        description = description[:500] + "..."

    return (
        f"🆕 <b>{order['title']}</b>{price_line}\n\n"
        f"{description}"
    )


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(
        "Привет! Я слежу за новыми заказами на Kwork и присылаю уведомления "
        "с кнопками для перехода и генерации отклика."
    )


@dp.callback_query(F.data.startswith("gen:"))
async def on_generate_reply(callback: CallbackQuery) -> None:
    order_id = callback.data.split(":", 1)[1]

    order = get_order(order_id)

    if not order:
        await callback.answer(
            "Не нашёл данные по этому заказу :(",
            show_alert=True,
        )
        return

    await callback.answer("Генерирую отклик...")

    try:
        reply_text = await asyncio.to_thread(
            generate_reply,
            order["title"],
            order["description"],
            order.get("price", ""),
        )

    except Exception as e:
        logger.error("Ошибка генерации отклика: %s", e)

        await callback.message.answer(
            f"Ошибка генерации отклика: {e}"
        )

        return

    if not reply_text:
        logger.error(
            "Генератор вернул пустой текст отклика для заказа %s",
            order_id,
        )

        await callback.message.answer(
            "Не удалось сгенерировать отклик. Попробуйте позже."
        )

        return

    await callback.message.answer(reply_text)


@retry_on_network_error(max_retries=5, delay=3.0)
async def notify_new_order(order: dict) -> None:
    save_order(order)

    logger.info(
        "Отправка нового заказа %s в Telegram: title=%s",
        order["id"],
        order.get("title", ""),
    )

    await bot.send_message(
        chat_id=settings.TELEGRAM_CHAT_ID,
        text=_format_order_message(order),
        reply_markup=_order_keyboard(
            order["id"],
            order["url"],
        ),
    )

    logger.info(
        "Новый заказ %s отправлен в Telegram",
        order["id"],
    )


async def initialize_seen_orders() -> None:
    """
    Первый запуск после деплоя.

    Получаем текущие заказы Kwork и записываем их в базу,
    НО НЕ отправляем их в Telegram.

    Таким образом старые заказы становятся "известными",
    а отправляться будут только те, которые появятся
    после начала работы бота.
    """

    logger.info(
        "Первичная инициализация: получаю текущие заказы без отправки..."
    )

    try:
        current_orders = await fetch_new_orders()

        for order in current_orders:
            save_order(order)

        logger.info(
            "Первичная инициализация завершена. "
            "Старых заказов добавлено в базу: %d",
            len(current_orders),
        )

    except Exception as e:
        logger.error(
            "Ошибка первичной инициализации: %s",
            e,
        )


async def polling_loop() -> None:
    init_db()

    # ВАЖНО:
    # При запуске сначала запоминаем уже существующие заказы.
    # Они НЕ отправляются пользователю.
    await initialize_seen_orders()

    logger.info(
        "Мониторинг новых заказов запущен. "
        "Теперь отправляются только новые заказы."
    )

    while True:
        try:
            new_orders = await fetch_new_orders()

            if new_orders:
                logger.info(
                    "Найдено новых заказов: %d",
                    len(new_orders),
                )

                for order in new_orders:
                    await notify_new_order(order)

            else:
                logger.info(
                    "Новых заказов не найдено"
                )

        except Exception as e:
            logger.error(
                "Ошибка в polling_loop: %s",
                e,
            )

        await asyncio.sleep(settings.POLL_INTERVAL)


@retry_on_network_error(max_retries=5, delay=3.0)
async def run() -> None:
    await asyncio.gather(
        dp.start_polling(bot),
        polling_loop(),
    )
