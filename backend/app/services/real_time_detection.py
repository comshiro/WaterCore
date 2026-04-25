from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime

from backend.app.services.data_sources import get_sentinel1_vv_stats


# ----------------------------
# INPUT
# ----------------------------

@dataclass
class FloodDetectionInput:
    bbox: List[float]
    rainfall_anomaly: float  # 0–3 (ERA5/CDS)

    # optional future extension
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None


# ----------------------------
# SENTINEL SCENE (derived, NOT mocked)
# ----------------------------

@dataclass
class SentinelScene:
    scene_id: str
    acquisition_datetime: datetime
    bbox: List[float]
    vv_mean: float


# ----------------------------
# HELPERS
# ----------------------------

def _clamp(x: float, min_v: float = 0.0, max_v: float = 1.0) -> float:
    return max(min_v, min(max_v, x))


def compute_intensity(pre_vv: float, post_vv: float) -> float:
    # Directional intensity: only VV drops increase flood intensity.
    return _clamp(pre_vv - post_vv)


def compute_flood_extent(pre_vv: float, post_vv: float) -> float:
    """
    SAR flood proxy:
    stronger VV drop → more flooding
    """
    delta = pre_vv - post_vv
    return _clamp(delta * 5.0)


def normalize_rainfall(rainfall_anomaly: float) -> float:
    return _clamp(rainfall_anomaly / 3.0)


def estimate_water_height_m(flood_extent: float, intensity: float, rainfall: float) -> float:
    """
    Depth proxy in meters (not direct observed depth):
    combines SAR flood signal and rainfall anomaly into a conservative 0-3m range.
    """
    depth = 2.2 * flood_extent + 0.5 * intensity + 0.3 * rainfall
    return round(_clamp(depth, 0.0, 3.0), 3)


def estimate_confidence(pre_valid_ratio: float, post_valid_ratio: float, flood_extent: float) -> float:
    """Confidence rises with valid-pixel coverage and stronger directional flood signal."""
    coverage = _clamp(min(pre_valid_ratio, post_valid_ratio))
    signal = _clamp(flood_extent)
    confidence = 0.7 * coverage + 0.3 * signal
    return round(_clamp(confidence), 4)


# ----------------------------
# REAL SENTINEL-1 PIPELINE
# ----------------------------

def fetch_sentinel1_vv_pair(
    bbox: List[float],
    start: datetime,
    end: datetime
) -> tuple[float, float, float, float]:
    """
    REAL data pipeline hook.

    Uses Sentinel Hub via data_sources.py:

    - extracts VV mean for pre-period
    - extracts VV mean for post-period
    """

    mid = start + (end - start) / 2

    pre_vv, pre_valid_ratio = get_sentinel1_vv_stats(bbox, start, mid)
    post_vv, post_valid_ratio = get_sentinel1_vv_stats(bbox, mid, end)

    return pre_vv, post_vv, pre_valid_ratio, post_valid_ratio


# ----------------------------
# FINAL FLOOD SCORE
# ----------------------------

def compute_flood_assessment(data: FloodDetectionInput) -> Dict[str, float]:
    """
    Insurance-grade flood score (NO MOCKS).

    Inputs:
        - Sentinel-1 VV (real via Sentinel Hub)
        - rainfall anomaly (ERA5/CDS)

    Output:
        0.0 → no flood
        1.0 → severe flood
    """

    if data.start_datetime is None or data.end_datetime is None:
        raise ValueError("start_datetime and end_datetime are required for real Sentinel-1 analysis")

    pre_vv, post_vv, pre_valid_ratio, post_valid_ratio = fetch_sentinel1_vv_pair(
        data.bbox,
        data.start_datetime,
        data.end_datetime,
    )

    flood_extent = compute_flood_extent(pre_vv, post_vv)
    intensity = compute_intensity(pre_vv, post_vv)
    rainfall = normalize_rainfall(data.rainfall_anomaly)

    score = (
        0.60 * flood_extent +
        0.25 * intensity +
        0.15 * rainfall
    )

    confidence = estimate_confidence(pre_valid_ratio, post_valid_ratio, flood_extent)
    water_height_m = estimate_water_height_m(flood_extent, intensity, rainfall)

    return {
        "flood_score": round(_clamp(score), 4),
        "estimated_water_height_m": water_height_m,
        "confidence": confidence,
        "pre_vv": round(pre_vv, 4),
        "post_vv": round(post_vv, 4),
        "pre_valid_ratio": round(pre_valid_ratio, 4),
        "post_valid_ratio": round(post_valid_ratio, 4),
    }


def compute_flood_score(data: FloodDetectionInput) -> float:
    """Backward-compatible helper for existing callers expecting only a score."""
    return compute_flood_assessment(data)["flood_score"]