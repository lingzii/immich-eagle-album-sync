import logging

import anyio
from rich.logging import RichHandler
from rich.traceback import install
from services.scanner import start_sync_scanner
from services.server import start_bridge_server

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Service starting...")
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(start_sync_scanner)
            tg.start_soon(start_bridge_server)

    except Exception as e:
        logger.exception("Unhandled exception occurred", exc_info=e)

    finally:
        logger.info("Service shutdown complete.")


if __name__ == "__main__":
    try:
        install(show_locals=True)
        anyio.run(main)
    except KeyboardInterrupt:
        logger.info("Service stopped by user (KeyboardInterrupt)")
