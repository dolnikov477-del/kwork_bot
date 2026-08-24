import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from storage import init_db, start_cleanup_task
from bot import run

init_db()
# Start background cleanup task
start_cleanup_task()

if __name__ == "__main__":
    asyncio.run(run())
