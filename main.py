import asyncio
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from config import settings
from bot import run

if os.path.exists(settings.DB_PATH):
    os.remove(settings.DB_PATH)

if __name__ == "__main__":
    asyncio.run(run())
