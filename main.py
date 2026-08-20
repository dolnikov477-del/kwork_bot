import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from storage import init_db
from bot import run

init_db()

if __name__ == "__main__":
    asyncio.run(run())
