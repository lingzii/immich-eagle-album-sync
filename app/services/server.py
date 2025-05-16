import logging
from uuid import UUID

import anyio
from aiohttp import ClientSession, web
from utils.config import settings

logger = logging.getLogger(__name__)


def is_valid_asset_id(assetId: str) -> bool:
    try:
        return str(UUID(assetId, version=4)) == assetId
    except ValueError:
        return False


async def fetch_asset(session: ClientSession, path: str, params: dict | None = None):
    async with session.get(path, params=params) as res:
        if res.status != 200:
            return web.json_response(await res.json(), status=res.status)

        return web.Response(
            body=await res.read(),
            content_type=res.headers.get("Content-Type", "application/octet-stream"),
        )


async def handler(request: web.Request) -> web.Response:
    assetType = request.query.get("type", "")
    assetId = request.query.get("id", "")

    if not is_valid_asset_id(assetId):
        return web.json_response({"error": "Invalid assetId"}, status=400)

    async with ClientSession() as session:
        if assetType == "IMAGE":
            return await fetch_asset(
                session, f"/assets/{assetId}/thumbnail", params={"size": "thumbnail"}
            )
        elif assetType == "VIDEO":
            return await fetch_asset(session, f"/assets/{assetId}/video/playback")


async def start_bridge_server():
    app = web.Application()
    app.router.add_get("/", handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, settings.BRIDGE_HOST, settings.BRIDGE_PORT)
    await site.start()

    logger.info(f"Run bridge server at {settings.BRIDGE_HOST}:{settings.BRIDGE_PORT}")
    while True:
        anyio.sleep(3600)
