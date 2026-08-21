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
            [InlineKeyboardButton(text="🔗 Перейти к заказу", url=url)],
            [
                InlineKeyboardButton(
                    text="✨ Сгенерировать отклик",
                    callback_data=f"gen:{order_id}",
                )
            ],
        ]
    )


def _format_order_message(order: dict) -> str:
    parts = [f"🆕 {order['title']}"]
    if order.get("price"):
        parts.append(f"💰 Бюджет: {order['price']}")
    description = order.get("description", "")
    if len(description) > 300:
        description = description[:300] + "..."
    if description:
        parts.append(f"📝 {description}")
    return "\n\n".join(parts)


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
        await callback.answer("Не нашёл данные по этому заказу :(", show_alert=True)
        return

    await callback.answer("Генерирую отклик...")

    reply_text = ""
    for i in range(3):
        try:
            reply_text = await asyncio.to_thread(
                generate_reply, order["title"], order["description"], order.get("price", "")
            )
        except Exception as e:
            logger.error("Ошибка генерации отклика (попытка %d): %s", i + 1, e)
            await asyncio.sleep(1)
            continue

        if reply_text:
            break

        await asyncio.sleep(1)

    if not reply_text:
        logger.error("OpenRouter вернул пустой текст отклика для заказа %s", order_id)
        await callback.message.answer("Не удалось сгенерировать отклик. Попробуйте позже.")
        return

    try:
        await callback.message.answer(
            reply_text,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("Ошибка отправки AI-отклика для заказа %s: %s", order_id, e)
        await callback.message.answer("Не удалось отправить отклик. Попробуйте позже.")


@retry_on_network_error(max_retries=5, delay=3.0)
async def notify_new_order(order: dict) -> None:
    logger.info(
        "Отправка заказа %s в Telegram: title=%s",
        order["id"],
        order.get("title", ""),
    )
    try:
        await bot.send_message(
            chat_id=settings.TELEGRAM_CHAT_ID,
            text=_format_order_message(order),
            reply_markup=_order_keyboard(order["id"], order["url"]),
            parse_mode=None,
        )
    except Exception as e:
        logger.error("Ошибка отправки заказа %s: %s", order["id"], e)
        return
    logger.info("Заказ %s отправлен в Telegram", order["id"])
    save_order(order)


async def polling_loop() -> None:
    init_db()
    last_error_sent = False
    while True:
        try:
            await fetch_new_orders(on_new_order=notify_new_order)
            last_error_sent = False
        except Exception as e:
            logger.error("Ошибка в polling_loop: %s", e)
            if not last_error_sent:
                await bot.send_message(
                    chat_id=settings.TELEGRAM_CHAT_ID,
                    text="⚠️ Произошла ошибка в логах",
                )
                last_error_sent = True

        await asyncio.sleep(settings.POLL_INTERVAL)


@retry_on_network_error(max_retries=5, delay=3.0)
async def run() -> None:
    await asyncio.gather(
        dp.start_polling(bot),
        polling_loop(),
    )