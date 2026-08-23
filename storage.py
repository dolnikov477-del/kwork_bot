import json
import os
import logging
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)

SEEN_ORDERS_FILE = settings.SEEN_ORDERS_FILE
SEEN_ORDER_TTL_HOURS = settings.SEEN_ORDER_TTL_HOURS

_orders: dict[str, dict] = {}


def _cleanup_expired() -> None:
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


def init_db() -> None:
    global _orders
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
            logger.info("Загружено просмотренных заказов: %d", len(_orders))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Не удалось загрузить %s: %s", SEEN_ORDERS_FILE, e)
            _orders = {}
    else:
        _orders = {}
        logger.info("Файл %s не найден, начинаем с пустого списка", SEEN_ORDERS_FILE)


def is_seen(order_id: str) -> bool:
    if order_id not in _orders:
        return False
    order = _orders[order_id]
    seen_at = order.get("seen_at")
    if not seen_at:
        return True
    now = datetime.now(timezone.utc)
    if (now - datetime.fromisoformat(seen_at)).total_seconds() > SEEN_ORDER_TTL_HOURS * 3600:
        del _orders[order_id]
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
        os.makedirs(os.path.dirname(SEEN_ORDERS_FILE) or ".", exist_ok=True)
        tmp_path = SEEN_ORDERS_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"orders": list(_orders.values())}, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, SEEN_ORDERS_FILE)
        logger.debug("Сохранён заказ %s в %s", order_id, SEEN_ORDERS_FILE)
    except OSError as e:
        logger.error("Не удалось сохранить заказ %s в %s: %s", order_id, SEEN_ORDERS_FILE, e)


def get_order(order_id: str) -> dict | None:
    return _orders.get(order_id)


def has_any_seen() -> bool:
    return bool(_orders)
