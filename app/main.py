import logging

from rich.logging import RichHandler
from rich.traceback import install
from utils.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)
logger = logging.getLogger(__name__)


def main():
    print("Hello from immich-eagle-album-sync!")
    print(settings.EAGLE_API_URL)


if __name__ == "__main__":
    try:
        install(show_locals=True)
        main()
    except KeyboardInterrupt:
        logger.info("Service stopped by user (KeyboardInterrupt)")
