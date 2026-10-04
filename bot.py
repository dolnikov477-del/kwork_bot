import asyncio
import logging
from functools import wraps

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError
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
from storage import get_order, init_db, save_order, is_seen

logger = logging.getLogger(__name__)


async def safe_send_message(bot: Bot, chat_id: int | str, text: str, **kwargs):
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        await bot.send_message(chat_id, text, **kwargs)
    except TelegramServerError:
        await asyncio.sleep(10)
        await bot.send_message(chat_id, text, **kwargs)


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
    default=DefaultBotProperties(parse_mode=None),
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


def _format_order_message(order: dict, reply_text: str = "", source: str = "") -> str:
    """Форматирует сообщение с заказом и опционально с откликом."""
    parts = [f"🆕 {order['title']}"]
    if order.get("price"):
        parts.append(f"💰 Бюджет: {order['price']}")
    description = order.get("description", "")
    if len(description) > 300:
        description = description[:300] + "..."
    if description:
        parts.append(f"📝 {description}")

    if reply_text:
        parts.append("─" * 30)
        parts.append(f"🤖 <b>Отклик ({'ИИ' if source == 'ai' else 'шаблон'})</b>:")
        parts.append(reply_text)
        if source == "fallback_template":
            parts.append("\n⚠️ <b>ИИ недоступен, подставлен шаблонный отклик.</b> Проверь и поправь перед отправкой.")

    return "\n\n".join(parts)


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return parts


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(
        "Привет! Я слежу за новыми заказами на Kwork и присылаю уведомления "
        "с кнопками для перехода и генерации отклика."
    )


@dp.callback_query(F.data.startswith("gen:"))
async def on_generate_reply(callback: CallbackQuery) -> None:
    # СРАЗУ отвечаем на callback, чтобы не было "query is too old"
    await callback.answer()

    order_id = callback.data.split(":", 1)[1]
    order = get_order(order_id)

    if not order:
        await callback.message.answer("Не нашёл данные по этому заказу :(")
        return

    # Отправляем сообщение "Генерирую..."
    status_msg = await callback.message.answer("⏳ Генерирую отклик...")

    reply_text = ""
    source = "fallback_template"

    try:
        reply_text, source = await generate_reply(
            order["title"], order["description"], order.get("price", "")
        )
    except Exception as e:
        logger.error("Ошибка генерации отклика для заказа %s: %s", order_id, e)
        reply_text = ""
        source = "fallback_template"

    # Удаляем статус-сообщение
    try:
        await status_msg.delete()
    except Exception:
        pass

    if not reply_text or not reply_text.strip():
        logger.error("Не удалось сгенерировать валидный отклик для заказа %s", order_id)
        await callback.message.answer("Не удалось сгенерировать отклик. Попробуйте позже.")
        return

    logger.info("Длина %s-отклика для заказа %s: %d символов", source, order_id, len(reply_text))

    try:
        # Формируем сообщение с заказом и откликом
        full_message = _format_order_message(order, reply_text, source)
        parts = _split_message(full_message, max_len=4000)
        for part in parts:
            await callback.message.answer(
                part,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
    except Exception as e:
        logger.error("Ошибка отправки отклика для заказа %s: %s", order_id, e)
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
    finally:
        save_order(order)


async def polling_loop() -> None:
    """Основной цикл парсинга: стримит заказы и шлёт их сразу по мере появления."""
    logger.info("Запуск цикла парсинга с интервалом %d сек", settings.POLL_INTERVAL)
    while True:
        try:
            async for order in fetch_new_orders():
                order_id = order.get("id")
                if order_id and is_seen(order_id):
                    logger.debug("Пропуск заказа %s: уже в памяти", order_id)
                    continue
                try:
                    await notify_new_order(order)
                except Exception as e:
                    logger.error("Ошибка при отправке заказа %s: %s", order.get('id'), e)
        except Exception as e:
            logger.exception("Ошибка в цикле парсинга: %s", e)

        logger.debug("Ожидание %d секунд до следующего цикла", settings.POLL_INTERVAL)
        await asyncio.sleep(settings.POLL_INTERVAL)


@retry_on_network_error(max_retries=5, delay=3.0)
async def run() -> None:
    from storage import start_cleanup_task
    start_cleanup_task()
    await asyncio.gather(
        dp.start_polling(bot),
        polling_loop(),
    )