import os
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    EAGLE_API_SCHEMA: str = Field("http", pattern="^(http|https)$")
    EAGLE_API_HOST: str
    EAGLE_API_PORT: int = Field(41595, ge=1, le=65535)
    EAGLE_API_KEY: str

    @property
    def EAGLE_API_URL(self) -> str:
        parsed = urlparse(self.EAGLE_API_HOST)

        if not parsed.scheme:
            parsed = urlparse(f"{self.EAGLE_API_SCHEMA}://{self.EAGLE_API_HOST}")

        if not parsed.port:
            parsed = parsed._replace(netloc=f"{parsed.netloc}:{self.EAGLE_API_PORT}")

        return f"{parsed.geturl()}/api"

    class Config:
        env_file = ".env" if os.getenv("ENV") == "development" else None
        env_file_encoding = "utf-8"


settings = Settings()
