from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WaterCore - weilding Copernicus API"
    app_env: str = "dev"
    app_debug: bool = True
    default_alert_threshold: float = 0.7
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:5500"
    copernicus_stac_url: str = "https://catalogue.dataspace.copernicus.eu/stac"
    copernicus_stac_timeout_seconds: int = 30
    copernicus_stac_token: str = ""
    sentinel_hub_base_url: str = "https://services.sentinel-hub.com"
    sentinel_hub_token_url: str = "https://services.sentinel-hub.com/oauth/token"
    sentinel_hub_process_path: str = "/api/v1/process"
    sentinel_hub_timeout_seconds: int = 60
    sentinel_hub_client_id: str = ""
    sentinel_hub_client_secret: str = ""
    cds_api_url: str = "https://cds.climate.copernicus.eu/api/v2"
    cds_api_key: str = ""
    cds_request_timeout_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
