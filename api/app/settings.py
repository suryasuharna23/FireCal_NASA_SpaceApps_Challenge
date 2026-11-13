"""API configuration loaded from environment / root ``.env`` (NFR-08)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    firms_map_key: SecretStr = SecretStr("")
    data_uri: str = "./data/processed"
    max_aoi_km2: float = 1_000_000
    reference_years: str = "2003:2022"
    cors_origins: str = "http://localhost:5173"
    s3_endpoint: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr = SecretStr("")
    cache_ttl_seconds: int = 900
    max_points: int = 50_000
    log_level: str = "info"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def default_reference_years(self) -> tuple[int, int]:
        start, end = self.reference_years.split(":")
        return int(start), int(end)


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
