"""Pipeline configuration loaded from the root ``.env`` (see ``.env.example``)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from firecal.grid import GridSpec
from firecal.paths import DataPaths

NATURAL_EARTH = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    firms_map_key: str = ""
    firms_api_base: str = "https://firms.modaps.eosdis.nasa.gov/api"
    data_root: Path = Path("data")
    coverage_bbox: str = "-180,-90,180,90"
    grid_res_deg: float = 0.25
    modis_min_confidence: int = 30
    viirs_confidence: str = "nominal,high"
    calibration_period: str = "2013-01:2021-12"
    reference_years: str = "2003:2022"
    land_url: str = f"{NATURAL_EARTH}/ne_50m_land.geojson"
    ecoregions_path: Path | None = None
    log_level: str = "info"

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        west, south, east, north = (float(v) for v in self.coverage_bbox.split(","))
        return west, south, east, north

    @property
    def viirs_confidence_levels(self) -> list[str]:
        return [v.strip() for v in self.viirs_confidence.split(",") if v.strip()]

    @property
    def grid(self) -> GridSpec:
        return GridSpec(self.grid_res_deg)

    @property
    def paths(self) -> DataPaths:
        return DataPaths(self.data_root)


@lru_cache
def get_settings() -> PipelineSettings:
    return PipelineSettings()
