from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =========================
# RISK MODELS
# =========================

class RiskInput(BaseModel):
    """
    Supports both:
    - point-based risk (latitude + longitude)
    - future bbox/scene-based risk (optional bbox)
    """

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    bbox: Optional[List[float]] = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="Optional bounding box [min_lon, min_lat, max_lon, max_lat]",
    )

    rainfall_anomaly: float = Field(..., ge=0, le=3)
    soil_moisture_anomaly: float = Field(..., ge=0, le=3)

    flood_signal: float = Field(..., ge=0, le=1)
    vegetation_stress: float = Field(..., ge=0, le=1)


class RiskResponse(BaseModel):
    risk_score: float
    risk_level: str
    threshold: float
    factors: Dict[str, float]
    generated_at: datetime

    # future-proof additions
    source: Optional[str] = None
    input_mode: Literal["point", "bbox", "scene_aggregation"] = "point"
    confidence: Optional[float] = None


# =========================
# HEALTH
# =========================

class HealthResponse(BaseModel):
    status: str
    service: str


# =========================
# SCENE SEARCH
# =========================

class SceneSearchRequest(BaseModel):
    collection: str = "sentinel-1-grd"

    bbox: List[float] = Field(..., min_length=4, max_length=4)

    # FIX: unified datetime handling
    start_datetime: datetime
    end_datetime: datetime

    limit: int = Field(default=10, ge=1, le=100)

    cloud_cover_lte: Optional[float] = Field(default=None, ge=0, le=100)


class SceneItem(BaseModel):
    scene_id: str
    collection: Optional[str] = None
    acquisition_datetime: Optional[datetime] = None
    bbox: Optional[List[float]] = None
    cloud_cover: Optional[float] = None


class SceneSearchResponse(BaseModel):
    source: str
    count: int
    scenes: List[SceneItem]


# =========================
# BEST SCENE (optional future use)
# =========================

class BestSceneRequest(BaseModel):
    bbox: List[float] = Field(..., min_length=4, max_length=4)
    collection: str = "sentinel-1-grd"


class BestSceneResponse(BaseModel):
    source: str
    query_bbox: List[float]
    selected_scene: SceneItem
    coverage_ratio: float = Field(..., ge=0, le=1)
    considered_scenes: int = Field(..., ge=1)


# =========================
# DERIVED EO LAYERS
# =========================

class DerivedLayerRequest(BaseModel):
    layer_type: str = Field(default="ndwi")
    data_collection: str = Field(default="sentinel-2-l2a")

    bbox: List[float] = Field(..., min_length=4, max_length=4)

    # FIXED: datetime consistency
    start_datetime: datetime
    end_datetime: datetime

    width: int = Field(default=256, ge=64, le=1024)
    height: int = Field(default=256, ge=64, le=1024)

    output_mime: str = "image/png"


class DerivedLayerResponse(BaseModel):
    source: str
    layer_type: str
    data_collection: str
    mime_type: str
    image_base64: str


# =========================
# CLIMATE
# =========================

class ClimateBaselineRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    # FIXED: now consistent with rest of system
    start_datetime: datetime
    end_datetime: datetime


class ClimateBaselineResponse(BaseModel):
    source: str
    latitude: float
    longitude: float

    period_start: datetime
    period_end: datetime

    precipitation_mm: Optional[float] = None
    precipitation_anomaly: float

    temperature_mean_c: Optional[float] = None
    temperature_anomaly: float

    soil_moisture_anomaly: float

    data_quality: Literal["high", "medium", "fallback"] = "high"

    generated_at: datetime


# =========================
# FUTURE: SCENE AGGREGATION
# =========================

class SceneAggregationInput(BaseModel):
    """
    This is what your system is evolving toward:
    bbox → multiple scenes → aggregated risk
    """

    bbox: List[float] = Field(..., min_length=4, max_length=4)
    scenes: List[SceneItem]

    start_datetime: datetime
    end_datetime: datetime


class SceneAggregationResponse(BaseModel):
    aggregated_risk_score: float
    confidence: float
    scene_count: int
    method: str = "temporal_spatial_aggregation"


# =========================
# REAL-TIME FLOOD DETECTION
# =========================

class FloodDetectionRequest(BaseModel):
    """Real-time flood detection via Sentinel-1 VV analysis."""

    bbox: List[float] = Field(..., min_length=4, max_length=4, description="Bounding box [min_lon, min_lat, max_lon, max_lat]")
    start_datetime: datetime = Field(..., description="Analysis start (ISO 8601)")
    end_datetime: datetime = Field(..., description="Analysis end (ISO 8601)")
    rainfall_anomaly: float = Field(default=0.8, ge=0, le=3, description="Rainfall anomaly (0–3)")


class FloodDetectionResponse(BaseModel):
    """Flood detection output: Sentinel-1 VV + rainfall → flood score."""

    flood_score: float = Field(..., ge=0, le=1, description="0=no flood, 1=severe flood")
    bbox: List[float]
    centroid_latitude: float
    centroid_longitude: float
    analysis_start: datetime
    analysis_end: datetime
    generated_at: datetime