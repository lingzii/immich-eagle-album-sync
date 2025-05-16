import logging

import anyio
from rich.logging import RichHandler
from rich.traceback import install

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
        pass
    except Exception as e:
        logger.exception("Unhandled exception occurred", exc_info=e)
        raise
    finally:
        logger.info("Service shutdown complete.")


if __name__ == "__main__":
    try:
        install(show_locals=True)
        anyio.run(main)
    except KeyboardInterrupt:
        logger.info("Service stopped by user (KeyboardInterrupt)")
