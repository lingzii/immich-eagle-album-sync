import json
import logging
from datetime import datetime
from pathlib import Path

import anyio
from utils.config import settings

from services import EagleAsyncClient, receive_channel

logger = logging.getLogger(__name__)


def correction(metadata_path: Path, folderId: str, dt: datetime):
    with metadata_path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)
        metadata["btime"] = int(dt.timestamp())
        metadata["mtime"] = int(dt.timestamp())
        metadata["folders"] = [folderId]

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)


async def start_time_correction():
    async with EagleAsyncClient(
        base_url=settings.EAGLE_API_URL + "/api",
    ) as eagle:
        res = await eagle.get("/library/info")
        root = Path(res.json()["data"]["library"]["path"])

    async with receive_channel:
        async for assetId, folderId, dt in receive_channel:
            metadata_path = root / f"images/{assetId}.info/metadata.json"
            if not metadata_path.exists():
                logger.warning(f"Metadata file does not exist: {metadata_path}")
                continue

            try:
                await anyio.to_thread.run_sync(
                    correction,
                    metadata_path,
                    folderId,
                    dt := datetime.fromisoformat(dt),
                )
                logger.info(f"Change {assetId} datetime to {dt}")

            except Exception as e:
                logger.exception(f"Error correcting metadata for {metadata_path}: {e}")
