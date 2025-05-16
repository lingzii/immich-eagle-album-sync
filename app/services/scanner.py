import logging
import math

import anyio
import httpx
from utils.config import settings

logger = logging.getLogger(__name__)


class EagleAsyncClient(httpx.AsyncClient):
    def __init__(self, **kwargs):
        self.token = {"token": settings.EAGLE_API_KEY}
        super().__init__(base_url=settings.EAGLE_API_URL, **kwargs)

    async def get(self, url, *, params=None, **kwargs):
        merged_params = {**self.token, **(params or {})}
        return await super().get(url, params=merged_params, **kwargs)

    async def post(self, url, *, json=None, **kwargs):
        merged_json = {**self.token, **(json or {})}
        return await super().post(url, json=merged_json, **kwargs)


async def fetch_all_assets(client: httpx.AsyncClient, size: int = 1000) -> list[dict]:
    async def fetch(page: int) -> list[dict]:
        res = await client.post(
            "/search/metadata",
            json={"size": size, "isVisible": True, "page": page + 1},
        )
        return res.json()["assets"]["items"]

    total = (await client.get("/assets/statistics")).json()["total"]
    results: list[list[dict]] = [None] * math.ceil(total / size)

    async def fetch_and_store(page: int):
        results[page] = await fetch(page)

    async with anyio.create_task_group() as tg:
        for i in range(len(results)):
            tg.start_soon(fetch_and_store, i)

    return [item for page in results for item in page]


async def start_sync_scanner():
    while True:
        try:
            logger.info("Starting API scan for data changes...")
            async with (
                httpx.AsyncClient(
                    base_url=settings.IMMICH_API_URL,
                    headers={"x-api-key": settings.IMMICH_API_KEY},
                ) as immich,
                EagleAsyncClient() as eagle,
            ):
                pass

        except Exception as e:
            logger.exception(f"Error occurred during API scan: {e}")

        finally:
            await anyio.sleep(settings.SCAN_INTERVAL)
