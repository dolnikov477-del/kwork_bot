import sqlite3
from contextlib import closing

from config import settings


def init_db() -> None:
    with closing(sqlite3.connect(settings.DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_orders (
                id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                url TEXT,
                price TEXT
            )
            """
        )
        conn.commit()


def is_seen(order_id: str) -> bool:
    with closing(sqlite3.connect(settings.DB_PATH)) as conn:
        cur = conn.execute("SELECT 1 FROM seen_orders WHERE id = ?", (order_id,))
        return cur.fetchone() is not None


def save_order(order: dict) -> None:
    with closing(sqlite3.connect(settings.DB_PATH)) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO seen_orders (id, title, description, url, price)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                order["id"],
                order.get("title", ""),
                order.get("description", ""),
                order.get("url", ""),
                order.get("price", ""),
            ),
        )
        conn.commit()


def get_order(order_id: str) -> dict | None:
    with closing(sqlite3.connect(settings.DB_PATH)) as conn:
        cur = conn.execute(
            "SELECT id, title, description, url, price FROM seen_orders WHERE id = ?",
            (order_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "url": row[3],
            "price": row[4],
        }


def has_any_seen() -> bool:
    with closing(sqlite3.connect(settings.DB_PATH)) as conn:
        cur = conn.execute("SELECT 1 FROM seen_orders LIMIT 1")
        return cur.fetchone() is not None
