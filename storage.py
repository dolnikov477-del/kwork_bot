import json
import os
import logging

from config import settings

logger = logging.getLogger(__name__)

SEEN_ORDERS_FILE = settings.SEEN_ORDERS_FILE

_orders: dict[str, dict] = {}


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
            logger.info("Загружено просмотренных заказов: %d", len(_orders))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Не удалось загрузить %s: %s", SEEN_ORDERS_FILE, e)
            _orders = {}
    else:
        _orders = {}
        logger.info("Файл %s не найден, начинаем с пустого списка", SEEN_ORDERS_FILE)


def is_seen(order_id: str) -> bool:
    return order_id in _orders


def save_order(order: dict) -> None:
    order_id = order.get("id")
    if not order_id:
        return
    _orders[order_id] = order
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
