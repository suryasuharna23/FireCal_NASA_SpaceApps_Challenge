"""Request and response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


class AoiRequest(BaseModel):
    aoi: dict[str, Any] = Field(
        ..., description="GeoJSON Polygon/MultiPolygon geometry or Feature (WGS84)"
    )


class SeriesRequest(AoiRequest):
    start: str | None = Field(None, pattern=MONTH, description="First month, default 2001-01")
    end: str | None = Field(None, pattern=MONTH, description="Last month, default latest")
    reference_years: tuple[int, int] | None = Field(
        None, description="Years for the historical median, default REFERENCE_YEARS"
    )


class AoiInfo(BaseModel):
    area_km2: float
    cells: int


class MonthValue(BaseModel):
    year: int
    month: int
    value: float = Field(..., description="Harmonized hotspot count (MODIS-equivalent)")
    raw: float = Field(..., description="Unconverted count of the source sensor")
    n_modis: float
    n_viirs: float
    ci_low: float
    ci_high: float
    source: Literal["MODIS", "VIIRS"]
    provisional: bool = Field(..., description="Contains NRT data that is not final yet")
    median: float | None
    anomaly_pct: float | None
    percentile: float | None


class CalendarResponse(BaseModel):
    aoi: AoiInfo
    start: str
    end: str
    reference_years: tuple[int, int]
    transition_month: str
    data_version: str
    max_value: float
    months: list[MonthValue]
