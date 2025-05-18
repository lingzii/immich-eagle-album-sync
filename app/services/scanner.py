import logging
import math
import re
from datetime import datetime
from pathlib import Path

import anyio
import httpx
from utils.config import settings

from services import send_channel
from services.server import BRIDGE_URL

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
        send_channel,
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

                res = await eagle.get("/item/list", params={"limit": 1000000})
                eagle_assets = {i["annotation"]: i for i in res.json()["data"]}
                immich_assets = {i["id"]: i for i in await fetch_all_assets(immich)}
                logger.info(f"Fetched {len(eagle_assets)} assets from Eagle.")
                logger.info(f"Fetched {len(immich_assets)} assets from Immich.")

                eagle_keys, immich_keys = eagle_assets.keys(), immich_assets.keys()

                async def add_asset(
                    assetType: str, assetId: str, name: str, localDateTime: datetime
                ):
                    if year := str(localDateTime.year) not in default_folders:
                        res = await eagle.post("/folder/create", json={"folderName": year})
                        if res.is_success:
                            default_folders[year] = res.json()["id"]
                            logger.debug(f"Create folder {year}: {res.json()['id']}")
                        else:
                            logger.error(f"Create folder {year} failed: {res.text}")

                    res = await eagle.post(
                        "/item/addFromURL",
                        json={
                            "url": f"{BRIDGE_URL}/?type={assetType}&id={assetId}",
                            "annotation": assetId,
                            "name": Path(name).stem,
                        },
                    )
                    if res.is_success:
                        logger.debug(f"Asset {assetId} added successfully.")
                    else:
                        logger.error(f"Failed to add asset {assetId}: {res.text}")

                # Add new assets to Eagle
                async with anyio.create_task_group() as tg:
                    for i in map(immich_assets.get, immich_keys - eagle_keys):
                        localDateTime = datetime.fromisoformat(i["localDateTime"])
                        tg.start_soon(
                            add_asset, i["type"], i["id"], i["originalFileName"], localDateTime
                        )

                # Delete assets from Eagle
                if itemIds := [i["id"] for i in map(eagle_assets.get, eagle_keys - immich_keys)]:
                    res = await eagle.post("/item/moveToTrash", json={"itemIds": itemIds})
                    if res.is_success:
                        logger.debug(f"Assets moved to trash: {itemIds}")
                    else:
                        logger.error(f"Failed to move assets to trash: {res.text}")

                eagle_albums = {}  # {eagle_album_id: {immich_asset_ids}}
                for k in eagle_keys & immich_keys:
                    asset = eagle_assets[k]
                    if asset["folders"]:
                        for i in asset["folders"]:
                            if i in eagle_albumId_relate_name:
                                eagle_albums.setdefault(i, set()).add(k)
                    else:
                        localDateTime = datetime.fromisoformat(immich_assets[k]["localDateTime"])
                        year = str(localDateTime.year)
                        await send_channel.send(
                            (
                                asset["id"],
                                default_folders[year],
                                immich_assets[k]["fileCreatedAt"],
                            )
                        )

                res = await immich.get("/albums")
                eagle_albumId_relate_immich_albumId = {
                    i["description"]: i["id"] for i in res.json()
                }
                immich_keys, eagle_keys = (
                    eagle_albumId_relate_immich_albumId.keys(),
                    eagle_albumId_relate_name.keys(),
                )

                # Create new albums in Immich
                async def create_album(k):
                    res = await immich.post(
                        "/albums",
                        json={
                            "albumName": eagle_albumId_relate_name[k],
                            "assetIds": eagle_albums.get(k, []),
                            "description": k,
                        },
                    )
                    if res.is_success:
                        logger.debug(f"Album {i} created successfully.")
                    else:
                        logger.error(f"Failed to create album {i}: {res.text}")

                # Delete albums from Immich
                async def delete_album(k):
                    res = await immich.delete(f"/albums/{eagle_albumId_relate_immich_albumId[k]}")
                    if res.is_success:
                        logger.debug(f"Album {i} deleted successfully.")
                    else:
                        logger.error(f"Failed to delete album {i}: {res.text}")

                # Sync albums between Eagle and Immich
                async def sync_albums(k):
                    url = f"/albums/{eagle_albumId_relate_immich_albumId[k]}"
                    res = await immich.get(url)
                    immich_album_assetIds = {i["id"] for i in res.json()["assets"]}
                    eagle_album_assetIds = eagle_albums.get(k, set())

                    # Add assets to Immich album
                    if ids := list(eagle_album_assetIds - immich_album_assetIds):
                        res = await immich.put(f"{url}/assets", json={"ids": ids})
                        if res.is_success:
                            logger.debug(f"Assets added to album {k} successfully.")
                        else:
                            logger.error(f"Failed to add assets to album {k}: {res.text}")

                    # Remove assets from Immich album
                    if ids := list(immich_album_assetIds - eagle_album_assetIds):
                        res = await immich.request("DELETE", f"{url}/assets", json={"ids": ids})
                        if res.is_success:
                            logger.debug(f"Assets removed from album {k} successfully.")
                        else:
                            logger.error(f"Failed to remove assets from album {k}: {res.text}")

                    async with anyio.create_task_group() as tg:
                        for i in immich_keys - eagle_keys:
                            tg.start_soon(create_album, i)
                        for i in eagle_keys - immich_keys:
                            tg.start_soon(delete_album, i)
                        for i in eagle_keys & immich_keys:
                            tg.start_soon(sync_albums, i)

            except Exception as e:
                logger.exception(f"Error occurred during API scan: {e}")

            finally:
                await anyio.sleep(settings.SCAN_INTERVAL)
