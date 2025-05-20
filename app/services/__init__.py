import anyio
import httpx
from utils.config import settings

send_channel, receive_channel = anyio.create_memory_object_stream(100)


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
