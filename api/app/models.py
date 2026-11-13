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


class ClimatologyMonth(BaseModel):
    month: int
    median: float | None
    p25: float | None
    p75: float | None
    current: float | None = Field(..., description="Value in the last year of the range")
    critical: bool


class AnnualTotal(BaseModel):
    year: int
    total: float
    rank: int = Field(..., description="1 = highest total in the range")
    complete: bool


class CurrentMonth(BaseModel):
    month: str
    value: float | None
    median: float | None
    anomaly_pct: float | None
    percentile: float | None
    provisional: bool


class Summary(BaseModel):
    total: float | None
    monthly_mean: float | None
    peak_month: int | None = Field(..., description="Calendar month with the highest median")
    max_year: int | None
    max_year_total: float | None
    current: CurrentMonth | None


class StatsResponse(BaseModel):
    aoi: AoiInfo
    start: str
    end: str
    reference_years: tuple[int, int]
    data_version: str
    climatology: list[ClimatologyMonth]
    critical_threshold: float | None
    critical_months: list[int]
    annual: list[AnnualTotal]
    summary: Summary
