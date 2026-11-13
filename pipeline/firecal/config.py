"""Pipeline configuration loaded from the root ``.env`` (see ``.env.example``)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from firecal.clean import CleanConfig
from firecal.grid import GridSpec
from firecal.harmonize import HarmonizeConfig, parse_month, parse_period
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
    static_mask_deg: float = 0.02
    calibration_period: str = "2013-01:2021-12"
    test_years: str = "2016,2019"
    transition_month: str = ""
    min_cell_detections: float = 50
    calibration_shrinkage: float = 100
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

    @property
    def clean_config(self) -> CleanConfig:
        return CleanConfig(
            modis_min_confidence=self.modis_min_confidence,
            viirs_confidence=tuple(self.viirs_confidence_levels),
            static_mask_deg=self.static_mask_deg,
        )

    @property
    def harmonize_config(self) -> HarmonizeConfig:
        start, end = parse_period(self.calibration_period)
        return HarmonizeConfig(
            calibration_start=start,
            calibration_end=end,
            test_years=tuple(int(y) for y in self.test_years.split(",") if y.strip()),
            min_cell_viirs=self.min_cell_detections,
            shrinkage=self.calibration_shrinkage,
            transition=parse_month(self.transition_month) if self.transition_month else None,
        )


@lru_cache
def get_settings() -> PipelineSettings:
    return PipelineSettings()
