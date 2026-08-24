import json
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

SEEN_ORDERS_FILE = settings.SEEN_ORDERS_FILE
SEEN_ORDER_TTL_HOURS = settings.SEEN_ORDER_TTL_HOURS
MAX_SEEN_ORDERS = settings.MAX_SEEN_ORDERS
SEEN_ORDER_MAX_AGE_DAYS = settings.SEEN_ORDER_MAX_AGE_DAYS

_orders: dict[str, dict] = {}
_cleanup_lock = asyncio.Lock()
_last_cleanup = datetime.now(timezone.utc)
_CLEANUP_INTERVAL_HOURS = 1  # Run cleanup at least once per hour


def _cleanup_expired() -> None:
    global _orders
    now = datetime.now(timezone.utc)
    expired = [
        order_id
        for order_id, order in _orders.items()
        if order.get("seen_at")
        and (now - datetime.fromisoformat(order["seen_at"])).total_seconds()
        > SEEN_ORDER_TTL_HOURS * 3600
    ]
    for order_id in expired:
        del _orders[order_id]
    if expired:
        logger.info("Удалено просмотренных заказов по TTL: %d", len(expired))


def _cleanup_if_needed() -> None:
    global _orders
    if len(_orders) <= MAX_SEEN_ORDERS:
        return
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - (SEEN_ORDER_MAX_AGE_DAYS * 24 * 3600)
    to_remove = []
    for order_id, order in _orders.items():
        seen_at = order.get("seen_at")
        if not seen_at:
            continue
        try:
            ts = datetime.fromisoformat(seen_at).timestamp()
        except Exception:
            continue
        if ts < cutoff:
            to_remove.append(order_id)
    for order_id in to_remove:
        del _orders[order_id]
    if to_remove:
        logger.info("Удалено старых заказов при превышении лимита %d: %d", MAX_SEEN_ORDERS, len(to_remove))


async def _periodic_cleanup() -> None:
    """Periodically clean up expired orders"""
    while True:
        try:
            await asyncio.sleep(3600)  # Check every hour
            async with _cleanup_lock:
                _cleanup_expired()
        except Exception as e:
            logger.error("Ошибка при периодической очистке: %s", e)


def init_db() -> None:
    global _orders, _last_cleanup
    if os.path.exists(SEEN_ORDERS_FILE):
        try:
            with open(SEEN_ORDERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _orders = {
                    order["id"]: order
                    for order in data.get("orders", [])
                    if order.get("id")
                }
            _cleanup_expired()
            _cleanup_if_needed()
            _last_cleanup = datetime.now(timezone.utc)
            logger.info("Загружено просмотренных заказов: %d", len(_orders))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Не удалось загрузить %s: %s", SEEN_ORDERS_FILE, e)
            _orders = {}
    else:
        _orders = {}
        logger.info("Файл %s не найден, начинаем с пустого списка", SEEN_ORDERS_FILE)
        # Ensure the directory exists for future writes
        dir_name = os.path.dirname(SEEN_ORDERS_FILE)
        if dir_name and not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name, exist_ok=True)
                logger.info("Создана директория для хранения заказов: %s", dir_name)
            except OSError as e:
                logger.error("Не удалось создать директорию %s: %s", dir_name, e)


def is_seen(order_id: str) -> bool:
    if order_id not in _orders:
        return False
    order = _orders[order_id]
    seen_at = order.get("seen_at")
    if not seen_at:
        return True
    now = datetime.now(timezone.utc)
    if (now - datetime.fromisoformat(seen_at)).total_seconds() > SEEN_ORDER_TTL_HOURS * 3600:
        return False
    return True


def save_order(order: dict) -> None:
    order_id = order.get("id")
    if not order_id:
        return
    stored = dict(order)
    stored["seen_at"] = datetime.now(timezone.utc).isoformat()
    _orders[order_id] = stored
    try:
        dir_name = os.path.dirname(SEEN_ORDERS_FILE)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            logger.info("Создана директория для хранения заказов: %s", dir_name)
        tmp_path = SEEN_ORDERS_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"orders": list(_orders.values())}, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, SEEN_ORDERS_FILE)
        logger.info("Сохранён заказ %s в %s", order_id, SEEN_ORDERS_FILE)
        logger.info("Сохранено заказов: %d", len(_orders))
        _cleanup_if_needed()
    except OSError as e:
        logger.error("Не удалось сохранить заказ %s в %s: %s", order_id, SEEN_ORDERS_FILE, e)


def get_order(order_id: str) -> dict | None:
    return _orders.get(order_id)


def has_any_seen() -> bool:
    return bool(_orders)


# Start periodic cleanup when module is imported
# Note: In a real application, you'd want to manage this lifecycle better
# For now, we'll start it when first used
_cleanup_task: Optional[asyncio.Task] = None


def start_cleanup_task():
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        try:
            _cleanup_task = asyncio.create_task(_periodic_cleanup())
        except RuntimeError:
            # No running event loop, task will be started later
            pass