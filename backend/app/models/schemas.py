from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, Field


class RiskInput(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    rainfall_anomaly: float = Field(..., ge=0, le=3, description="Normalized rainfall anomaly")
    soil_moisture_anomaly: float = Field(..., ge=0, le=3, description="Normalized soil moisture anomaly")
    flood_signal: float = Field(..., ge=0, le=1, description="Flood indicator from EO data")
    vegetation_stress: float = Field(..., ge=0, le=1, description="Vegetation stress proxy")


class RiskResponse(BaseModel):
    risk_score: float
    risk_level: str
    threshold: float
    factors: Dict[str, float]
    generated_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str


class SceneSearchRequest(BaseModel):
    collection: str = Field(default="sentinel-1-grd", description="STAC collection ID")
    bbox: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box as [min_lon, min_lat, max_lon, max_lat]",
    )
    start_datetime: datetime = Field(..., description="Search start datetime (ISO 8601)")
    end_datetime: datetime = Field(..., description="Search end datetime (ISO 8601)")
    limit: int = Field(default=10, ge=1, le=100)
    cloud_cover_lte: float | None = Field(default=None, ge=0, le=100)


class SceneItem(BaseModel):
    scene_id: str
    collection: str | None = None
    acquisition_datetime: datetime | None = None
    bbox: List[float] | None = None
    cloud_cover: float | None = None


class SceneSearchResponse(BaseModel):
    source: str
    count: int
    scenes: List[SceneItem]


class DerivedLayerRequest(BaseModel):
    layer_type: str = Field(default="ndwi", description="ndwi | ndvi | flood_proxy_s1")
    data_collection: str = Field(default="sentinel-2-l2a", description="Sentinel Hub data collection")
    bbox: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box as [min_lon, min_lat, max_lon, max_lat]",
    )
    start_datetime: datetime = Field(..., description="Start datetime (ISO 8601)")
    end_datetime: datetime = Field(..., description="End datetime (ISO 8601)")
    width: int = Field(default=256, ge=64, le=1024)
    height: int = Field(default=256, ge=64, le=1024)
    output_mime: str = Field(default="image/png", description="image/png | image/tiff")


class DerivedLayerResponse(BaseModel):
    source: str
    layer_type: str
    data_collection: str
    mime_type: str
    image_base64: str


class ClimateBaselineRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    start_date: str = Field(..., description="Start date as YYYY-MM-DD")
    end_date: str = Field(..., description="End date as YYYY-MM-DD")


class ClimateBaselineResponse(BaseModel):
    source: str
    latitude: float
    longitude: float
    period_start: str
    period_end: str
    precipitation_mm: float | None = Field(None, description="Total precipitation in mm")
    precipitation_anomaly: float = Field(..., description="Deviation from long-term mean (normalized)")
    temperature_mean_c: float | None = Field(None, description="Mean temperature in Celsius")
    temperature_anomaly: float = Field(..., description="Deviation from long-term mean (normalized)")
    soil_moisture_anomaly: float = Field(..., description="Soil moisture deviation (normalized)")
    data_quality: str = Field(default="high", description="high | medium | fallback")
    generated_at: datetime
