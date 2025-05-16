import logging
import math
import re

import anyio
import httpx
from utils.config import settings

logger = logging.getLogger(__name__)


class EagleAsyncClient(httpx.AsyncClient):
    def __init__(self, *, base_url: str = "", **kwargs):
        self.token = {"token": settings.EAGLE_API_KEY}
        super().__init__(base_url=base_url, **kwargs)

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
    async with (
        EagleAsyncClient(
            base_url=settings.EAGLE_API_URL + "/api",
        ) as eagle,
        httpx.AsyncClient(
            base_url=settings.IMMICH_API_URL + "/api",
            headers={"x-api-key": settings.IMMICH_API_KEY},
        ) as immich,
    ):
        while True:
            try:
                logger.info("Starting API scan for data changes...")

                # Get default folders and album folders
                default_folders, eagle_albumId_relate_name = {}, {}
                res = await eagle.get("/folder/list")
                for i in res.json()["data"]:
                    if re.match(r"^(1\d{3}|2\d{3})$", i["name"]):
                        default_folders[i["name"]] = i["id"]
                        for j in i["children"]:
                            eagle_albumId_relate_name[j["id"]] = j["name"]

                immich_assets = {i["id"]: i for i in await fetch_all_assets(immich)}
                logger.info(f"Fetched {len(immich_assets)} assets from Immich.")

            except Exception as e:
                logger.exception(f"Error occurred during API scan: {e}")

            finally:
                await anyio.sleep(settings.SCAN_INTERVAL)
