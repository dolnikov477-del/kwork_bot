import json
import os
from config import settings

SEEN_ORDERS_FILE = "seen_orders.json"

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
        except (json.JSONDecodeError, OSError):
            _orders = {}
    else:
        _orders = {}


def is_seen(order_id: str) -> bool:
    return order_id in _orders


def save_order(order: dict) -> None:
    order_id = order.get("id")
    if not order_id:
        return
    _orders[order_id] = order
    try:
        with open(SEEN_ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"orders": list(_orders.values())}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def get_order(order_id: str) -> dict | None:
    return _orders.get(order_id)


def has_any_seen() -> bool:
    return bool(_orders)
