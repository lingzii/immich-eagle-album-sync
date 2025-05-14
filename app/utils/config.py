import os
from urllib.parse import urlparse

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    EAGLE_API_SCHEMA: str = Field("http", pattern="^(http|https)$")
    EAGLE_API_HOST: str
    EAGLE_API_PORT: int = Field(41595, ge=1, le=65535)
    EAGLE_API_KEY: str

    IMMICH_API_SCHEMA: str = Field("http", pattern="^(http|https)$")
    IMMICH_API_HOST: str
    IMMICH_API_PORT: int = Field(2283, ge=1, le=65535)
    IMMICH_API_KEY: str

    def _API_URL(self, schema: str, host: str, port: int) -> str:
        parsed = urlparse(host)

        if not parsed.scheme:
            parsed = urlparse(f"{schema}://{host}")

        if not parsed.port:
            parsed = parsed._replace(netloc=f"{parsed.netloc}:{port}")

        return parsed.geturl()

    @property
    def EAGLE_API_URL(self) -> str:
        return self._API_URL(
            self.EAGLE_API_SCHEMA, self.EAGLE_API_HOST, self.EAGLE_API_PORT
        )

    @property
    def IMMICH_API_URL(self) -> str:
        return self._API_URL(
            self.IMMICH_API_SCHEMA, self.IMMICH_API_HOST, self.IMMICH_API_PORT
        )

    def validate_connect(self):
        res = httpx.get(self.EAGLE_API_URL, params={"token": self.EAGLE_API_KEY})
        if res.is_error:
            raise ValueError(f"Invalid Eagle API URL: {self.EAGLE_API_URL}")
        res = httpx.get(self.IMMICH_API_URL, headers={"x-api-key": self.IMMICH_API_KEY})
        if res.is_error:
            raise ValueError(f"Invalid Immich API URL: {self.IMMICH_API_URL}")

    class Config:
        env_file = ".env" if os.getenv("ENV") == "development" else None
        env_file_encoding = "utf-8"


settings = Settings()
settings.validate_connect()
